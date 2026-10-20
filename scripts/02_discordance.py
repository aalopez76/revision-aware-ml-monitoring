"""G2: the discordance of recommendations across the 2x2 of information.

The gate. Everything before it built the chain; this is the one figure the
project exists to produce, and it is allowed to come out small.

    N1 = D(11, 00)

the proportion of eligible cuts at which the recommendation under both kinds of
information differs from the recommendation under neither. It is called
**discordance of recommendations** and never "value of information": that has a
precise decision-theoretic meaning -- expected utility gained by observing a
signal before deciding -- and this is not that. It measures that the
recommendation changed, not that it improved. It is not a false-alarm rate
either, because a recommendation that moves under a contrast does not identify
the cause of the original.

Four arms, crossed and not chained, with everything else identical at the same
cut: `d_00` has neither factor, `d_10` has revisions, `d_01` has coverage,
`d_11` has both. A sequential ablation would measure coverage *conditional on*
revisions having been added first, and that number depends on the order.

What governs this run is `config/g2_signals.json`, sealed into the manifest as
`selection_config_sha256`. It declares the two signals, the alarm grids, the
minimum support at which N1 is estimable, and the criterion that authorizes G3 --
all of it before this script was first run, which is the only reason the gate
means anything.

Three things about the denominator, because it is where this kind of measurement
usually goes wrong:

* **It is exogenous.** A cut is eligible by source, model and data: an as-of
  state exists, it is complete, a forecast is producible, and the target label
  has matured. Requiring that all four arms emit a "normal" decision would
  condition on a post-treatment variable, and then the information being
  measured would select its own denominator.
* **ABSTENERSE is a category, not a missing observation.** It is counted.
* **One row per distinct target week**, keeping the earliest origin at which
  that week became forecastable. P2 measured that a seven-week publication
  outage made one week the target of seven origins; a calendar rule collapses
  them, so the kept row cannot depend on which origin scored better.

Evidence class: **E2, controlled replay.** The forecasts are reconstructed from
as-of states rather than read from the immutable predictions G1 issued, because
a naive forecast is deterministic given the state and no run ever issued one at
these 60-odd origins. A replay reconstructed today does not demonstrate that
this system ran then, and it is labelled accordingly.

Cost: two `/archive/` requests. Every cut is derived locally.
"""

from __future__ import annotations

import itertools
import json
import math
from collections import Counter
from datetime import UTC, date, datetime, timedelta

import pandas as pd

from revmon import evidence, sources
from revmon.evidence import Modality, RunManifest
from revmon.forecasting import (
    ForecastError,
    LossScale,
    calibrate_scale,
    forecast,
    scaled_loss,
)
from revmon.monitoring import (
    ABSTAIN,
    ARMS,
    Thresholds,
    coverage_drop,
    recommend,
    revision_magnitude,
)
from revmon.panel import as_of_view, fetch_triangle_as_of, visible_triangle
from revmon.temporal import (
    SATURDAY,
    Completeness,
    MaturityPolicy,
    ReplayMode,
    scheduled_cut,
)

CONFIG = sources.ROOT / "config" / "g2_signals.json"

#: Where development ended, for the fourth time in this repository and with the
#: same value: the thresholds this script applies were chosen there, so the
#: period it evaluates begins after it.
DEVELOPMENT_THROUGH = date(2025, 6, 30)

#: The retrospective calibration window that fixed `s_dev`, unchanged. Never
#: recomputed with later data: a denominator that moves with the future can be
#: fitted.
CALIBRATION = (date(2024, 11, 19), date(2025, 6, 30))

UNIVERSE_FROM = date(2024, 11, 1)
NOMINAL_LAG_DAYS = 7


def load_config() -> dict:
    """The declared configuration. Read, never written: this script is governed by it."""
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def wilson(successes: int, total: int, z: float = 1.959964) -> tuple[float, float] | None:
    """Wilson score interval, declared in the config rather than chosen here.

    A normal approximation is wrong near 0 and 1, and a discordance may well sit
    there -- a saturated signal would put it at 1 and an inert one at 0, which
    are exactly the two outcomes this gate has to be able to report honestly.
    """
    if total <= 0:
        return None
    p = successes / total
    denominator = 1 + z**2 / total
    centre = (p + z**2 / (2 * total)) / denominator
    half = z * math.sqrt(p * (1 - p) / total + z**2 / (4 * total**2)) / denominator
    return round(max(0.0, centre - half), 6), round(min(1.0, centre + half), 6)


def _spread(values: list[float | None]) -> dict:
    """What a signal actually did over the evaluated weeks, so the alarm can be read."""
    present = sorted(v for v in values if v is not None)
    if not present:
        return {"n": len(values), "n_missing": len(values)}
    middle = len(present) // 2
    return {
        "n": len(values),
        "n_missing": len(values) - len(present),
        "min": round(present[0], 6),
        "median": round(
            present[middle]
            if len(present) % 2
            else (present[middle - 1] + present[middle]) / 2,
            6,
        ),
        "max": round(present[-1], 6),
    }


def authorizes_g3(
    n1: dict, support: int, *, min_support: int, floor: float = 0.10
) -> bool:
    """The declared gate criterion, as a function so it can be tested.

    The **lower** Wilson bound is compared against the floor, not the point
    estimate, so that a large discordance measured on thin support does not open
    G3. Declared in `config/g2_signals.json` before N1 was computed; a gate
    decided after seeing the number it judges is not a gate.
    """
    if support < min_support:
        return False
    interval = n1.get("wilson_95")
    if not interval:
        return False
    return interval[0] > floor


def candidate_cuts(first: date, last: date) -> list[date]:
    cursor = scheduled_cut(first)
    if cursor < first:
        cursor += timedelta(days=7)
    out = []
    while cursor <= last:
        out.append(cursor)
        cursor += timedelta(days=7)
    return out


def truth_by_week(triangle: pd.DataFrame, evaluated_at: date, policy: MaturityPolicy) -> dict:
    """The mature label for each week, as seen now. One label for every arm."""
    latest, _ = as_of_view(triangle, evaluated_at, ReplayMode.PUBLIC_REPLAY)
    labels: dict[date, float] = {}
    for row in latest.itertuples():
        week = pd.Timestamp(row.event_week_end).date()
        if policy.is_eligible(week, evaluated_at):
            labels[week] = float(row.value)
    return labels


def measure_cut(
    cut: date,
    target: pd.DataFrame,
    coverage: pd.DataFrame,
    *,
    policy: MaturityPolicy,
    signals: dict,
) -> dict | None:
    """Everything an arm could read at one cut, before any arm reads it.

    Returns `None` when the cut is not eligible, so eligibility is decided here,
    by source and data, and never by what a recommendation turned out to be.
    """
    state, completeness = as_of_view(target, cut, ReplayMode.PUBLIC_REPLAY)
    if completeness is not Completeness.COMPLETE or state.empty:
        return None

    weeks = sorted(pd.to_datetime(state["event_week_end"]).dt.date)
    last_visible = max(weeks)
    mature = [w for w in weeks if policy.is_eligible(w, cut)]
    anchor = max(mature) if mature else None

    try:
        issued = forecast(state, cut, model="naive")
    except ForecastError:
        return None

    triangle_at_cut = visible_triangle(target, cut, ReplayMode.PUBLIC_REPLAY)
    cover_state, _ = as_of_view(coverage, cut, ReplayMode.PUBLIC_REPLAY)

    magnitude, _ = revision_magnitude(
        triangle_at_cut,
        signals["R"]["lookback_weeks"],
        anchor_week=anchor,
    )
    fall = coverage_drop(
        cover_state, signals["C"]["lookback_weeks"], anchor_week=anchor
    )

    return {
        "cut": str(cut),
        "target_week": issued.target_week,
        "last_visible_week": str(last_visible),
        "publication_lag_days": (cut - last_visible).days,
        "y_pred": issued.value,
        "completeness": completeness.value,
        "revision_magnitude": magnitude,
        "coverage_drop": fall,
    }


def score_at(
    cut: date,
    rows: list[dict],
    labels: dict,
    scale: LossScale,
    policy: MaturityPolicy,
) -> tuple[float | None, int]:
    """Mean scaled loss over forecasts issued before this cut whose label matured.

    The same semantics as `monitoring.recent_loss`, over reconstructed forecasts
    rather than stored files, and with the same two exclusions: a forecast issued
    at this cut is not scored at it, because that would be scoring hindsight, and
    a label that had not matured is not scored at all.
    """
    losses = []
    for row in rows:
        if row["cut"] >= str(cut):
            continue
        week = date.fromisoformat(row["target_week"])
        if not policy.is_eligible(week, cut) or week not in labels:
            continue
        losses.append(scaled_loss(labels[week], row["y_pred"], scale))
    if not losses:
        return None, 0
    return round(sum(losses) / len(losses), 6), len(losses)


def one_row_per_target_week(rows: list[dict]) -> list[dict]:
    """A calendar rule, not a scoreboard rule. The same one P2 applied."""
    best: dict[str, dict] = {}
    for row in sorted(rows, key=lambda r: r["cut"]):
        best.setdefault(row["target_week"], row)
    return sorted(best.values(), key=lambda r: r["cut"])


def recommend_all_arms(row: dict, thresholds: Thresholds) -> dict[str, str]:
    """One recommendation per arm at one cut, with everything else identical."""
    out = {}
    for arm in ARMS:
        recommendation = recommend(
            information=arm,
            thresholds=thresholds,
            completeness=Completeness.COMPLETE,
            loss=row["loss"],
            mature_labels=row["mature_labels"],
            revisions=row["revision_magnitude"],
            coverage_fall=row["coverage_drop"],
        )
        out[arm.arm] = recommendation.action
    return out


def discordance(decisions: list[dict[str, str]], left: str, right: str) -> dict:
    """D(left, right): the share of cuts where the two arms recommend differently."""
    total = len(decisions)
    changed = sum(1 for d in decisions if d[left] != d[right])
    return {
        "numerator": changed,
        "denominator": total,
        "estimate": round(changed / total, 6) if total else None,
        "wilson_95": wilson(changed, total),
    }


def contingency(decisions: list[dict[str, str]], left: str, right: str) -> dict:
    """Which recommendation became which. A rate hides the pattern; this shows it."""
    pairs = Counter((d[right], d[left]) for d in decisions)
    out: dict[str, dict[str, int]] = {}
    for (base, other), count in sorted(pairs.items()):
        out.setdefault(f"{right}={base}", {})[f"{left}={other}"] = count
    return out


def main() -> int:
    config = load_config()
    signals = config["signals"]
    policy = MaturityPolicy(days=config["unchanged_and_why"]["maturity_days"]["value"],
                            declared_in=config["declared_in"])

    ran_at = datetime.now(UTC).date()
    evaluated_at = scheduled_cut(ran_at)

    manifest = RunManifest.start(
        decision_as_of=str(evaluated_at),
        modality=Modality.HISTORICAL_REPLAY,
        config={
            "universe_from": str(UNIVERSE_FROM),
            "evaluation_from": str(DEVELOPMENT_THROUGH + timedelta(days=1)),
            "maturity_days": policy.days,
            "calibration_window": [str(CALIBRATION[0]), str(CALIBRATION[1])],
            "declared_in": config["declared_in"],
            "evidence_class": "E2 controlled replay: forecasts reconstructed, not issued",
        },
        selection_config=CONFIG,
    )

    print("fetching the target triangle once ...", flush=True)
    target, target_prov = fetch_triangle_as_of(evaluated_at)
    if target.empty:
        print("the archive returned nothing; G2 is NOT_VERIFIABLE")
        return 1
    print("fetching the coverage triangle once ...", flush=True)
    coverage, coverage_prov = fetch_triangle_as_of(
        evaluated_at, signal=sources.COVERAGE_PCT_SIGNAL
    )

    # The same scale P2 used, built the same way: an as-of state at the end of
    # the calibration window, so the denominator never sees the period it scales.
    calibration_state, _ = as_of_view(target, CALIBRATION[1], ReplayMode.PUBLIC_REPLAY)
    scale = calibrate_scale(
        calibration_state,
        window_from=CALIBRATION[0],
        window_to=CALIBRATION[1],
        policy=policy,
    )
    labels = truth_by_week(target, evaluated_at, policy)

    cuts = candidate_cuts(DEVELOPMENT_THROUGH + timedelta(days=1), evaluated_at)
    assert all(c.weekday() == SATURDAY for c in cuts), "Decision A: every origin is a Saturday"
    print(f"deriving {len(cuts)} evaluation cuts locally ...", flush=True)

    measured = []
    for cut in cuts:
        row = measure_cut(cut, target, coverage, policy=policy, signals=signals)
        if row is not None:
            measured.append(row)

    # Eligibility, decided before any arm reads anything: the label must have
    # matured and a loss must be computable from strictly earlier origins.
    eligible = []
    for row in measured:
        week = date.fromisoformat(row["target_week"])
        if week not in labels:
            continue
        loss, mature = score_at(
            date.fromisoformat(row["cut"]), measured, labels, scale, policy
        )
        eligible.append({**row, "loss": loss, "mature_labels": mature})

    deduplicated = one_row_per_target_week(eligible)

    cells = {}
    grid = list(
        itertools.product(signals["R"]["alarm_grid"], signals["C"]["alarm_grid"])
    )
    for r_alarm, c_alarm in grid:
        thresholds = Thresholds(
            loss_alarm=config["unchanged_and_why"]["loss_alarm"]["value"],
            revision_alarm=r_alarm,
            coverage_drop_alarm=c_alarm,
            min_mature_labels=config["unchanged_and_why"]["min_mature_labels"]["value"],
            declared_in=config["declared_in"],
            revision_statistic=signals["R"]["statistic"],
        )
        decisions = [recommend_all_arms(row, thresholds) for row in deduplicated]
        cells[f"R={r_alarm},C={c_alarm}"] = {
            "n1_d11_vs_d00": discordance(decisions, "d_11", "d_00"),
            "simple_effects": {
                "d10_vs_d00": discordance(decisions, "d_10", "d_00"),
                "d01_vs_d00": discordance(decisions, "d_01", "d_00"),
                "d11_vs_d10": discordance(decisions, "d_11", "d_10"),
                "d11_vs_d01": discordance(decisions, "d_11", "d_01"),
            },
            "action_counts": {
                arm.arm: dict(Counter(d[arm.arm] for d in decisions)) for arm in ARMS
            },
            "abstentions": {
                arm.arm: sum(1 for d in decisions if d[arm.arm] == ABSTAIN) for arm in ARMS
            },
        }

    primary_key = f"R={signals['R']['primary_alarm']},C={signals['C']['primary_alarm']}"
    primary_thresholds = Thresholds(
        loss_alarm=config["unchanged_and_why"]["loss_alarm"]["value"],
        revision_alarm=signals["R"]["primary_alarm"],
        coverage_drop_alarm=signals["C"]["primary_alarm"],
        min_mature_labels=config["unchanged_and_why"]["min_mature_labels"]["value"],
        declared_in=config["declared_in"],
        revision_statistic=signals["R"]["statistic"],
    )
    primary_decisions = [recommend_all_arms(row, primary_thresholds) for row in deduplicated]

    # The two interaction contrasts, reported and never summed: discordance is a
    # non-additive functional of the arms, so these need not agree and neither is
    # a linear term. They are descriptive.
    simple = cells[primary_key]["simple_effects"]
    contrasts = {
        "coverage_given_revisions_minus_coverage_alone": round(
            (simple["d11_vs_d10"]["estimate"] or 0) - (simple["d01_vs_d00"]["estimate"] or 0), 6
        ),
        "revisions_given_coverage_minus_revisions_alone": round(
            (simple["d11_vs_d01"]["estimate"] or 0) - (simple["d10_vs_d00"]["estimate"] or 0), 6
        ),
        "note": (
            "Descriptive differences of discordances, not interaction terms of a "
            "model. They are not added together and neither is subtracted from N1."
        ),
    }

    # Decision B asked for the horizon strata, and they turn out to be vacuous on
    # deduplicated rows: the calendar rule keeps the **earliest** origin for a
    # week, which is the one with the shortest lag, so a delayed origin is kept
    # only when no earlier one targeted the same week. Both readings are reported
    # rather than picking the one with support, because each is misleading alone:
    # the deduplicated stratum is empty by construction, and the undeduplicated
    # one counts the same week several times.
    strata: dict[str, dict] = {"deduplicated": {}, "undeduplicated_origins": {}}
    undeduplicated_decisions = [recommend_all_arms(r, primary_thresholds) for r in eligible]
    for name, keep in (
        ("nominal", lambda lag: lag <= NOMINAL_LAG_DAYS),
        ("delayed", lambda lag: lag > NOMINAL_LAG_DAYS),
    ):
        indices = [i for i, r in enumerate(deduplicated) if keep(r["publication_lag_days"])]
        subset = [primary_decisions[i] for i in indices]
        strata["deduplicated"][name] = {
            "distinct_target_weeks": len(subset),
            "estimable": len(subset) >= config["n1"]["min_support_distinct_weeks"],
            "n1_d11_vs_d00": discordance(subset, "d_11", "d_00") if subset else None,
        }

        raw = [i for i, r in enumerate(eligible) if keep(r["publication_lag_days"])]
        raw_subset = [undeduplicated_decisions[i] for i in raw]
        strata["undeduplicated_origins"][name] = {
            "origins": len(raw_subset),
            "distinct_target_weeks": len({eligible[i]["target_week"] for i in raw}),
            "estimable": False,
            "n1_d11_vs_d00": discordance(raw_subset, "d_11", "d_00") if raw_subset else None,
        }

    strata["caveat"] = (
        "The deduplicated delayed stratum is empty by construction, not by "
        "measurement: keeping the earliest origin for each target week keeps the "
        "shortest lag. The undeduplicated counts are shown for completeness and "
        "are marked not estimable, because P2 measured that the delayed origins "
        "there are one publication outage seen six times, all targeting the same "
        "week with the same label. Neither reading supports a claim about how "
        "discordance varies with the effective horizon, and that is the honest "
        "answer to the stratification Decision B asked for."
    )

    n1 = cells[primary_key]["n1_d11_vs_d00"]
    support = len(deduplicated)
    min_support = config["n1"]["min_support_distinct_weeks"]
    estimable = support >= min_support
    lower = n1["wilson_95"][0] if n1["wilson_95"] else None
    authorizes = authorizes_g3(n1, support, min_support=min_support)

    payload = {
        "manifest": manifest.as_dict(),
        "provenance": {
            "target": target_prov.as_dict() if target_prov else None,
            "coverage": coverage_prov.as_dict() if coverage_prov else None,
        },
        "evidence_class": (
            "E2, controlled replay. The forecasts are reconstructed from as-of "
            "states; no run issued one at these origins, and a replay built today "
            "does not demonstrate that this system ran then."
        ),
        "loss_scale": scale.as_dict(),
        "support": {
            "candidate_cuts": len(cuts),
            "measured_cuts": len(measured),
            "eligible_origins": len(eligible),
            "distinct_target_weeks": support,
            "collapsed_by_calendar": len(eligible) - support,
            "min_support_distinct_weeks": config["n1"]["min_support_distinct_weeks"],
            "estimable": estimable,
        },
        "primary_cell": {
            "key": primary_key,
            "thresholds": primary_thresholds.as_dict(),
            "n1_d11_vs_d00": n1,
            "simple_effects": simple,
            "interaction_contrasts": contrasts,
            "contingency_d11_by_d00": contingency(primary_decisions, "d_11", "d_00"),
            "action_counts": cells[primary_key]["action_counts"],
            "abstentions": cells[primary_key]["abstentions"],
        },
        "signal_values_in_evaluation": {
            "revision_magnitude": _spread([r["revision_magnitude"] for r in deduplicated]),
            "coverage_drop": _spread([r["coverage_drop"] for r in deduplicated]),
            "caveat": (
                "The alarms were declared on development cuts ending 2025-06-30, "
                "and the two signals do not keep the same scale afterwards. The "
                "coverage drop reached 0.033225 points in development and 2.82 "
                "here, about eighty times larger, so a threshold set just above "
                "the development p90 sits far below the evaluation scale. The "
                "revision magnitude moves the other way: its whole evaluation "
                "range falls between two points of the declared grid, so R fires "
                "always at 0.005, partly at 0.01 and never at 0.02. This is what "
                "declaring on an unrepresentative window costs, and it is reported "
                "rather than fixed by re-declaring after the fact."
            ),
        },
        "threshold_sensitivity": {
            "n1_min": min(c["n1_d11_vs_d00"]["estimate"] for c in cells.values()),
            "n1_max": max(c["n1_d11_vs_d00"]["estimate"] for c in cells.values()),
            "gate_authorized_in_every_cell": all(
                (c["n1_d11_vs_d00"]["wilson_95"] or (0.0, 0.0))[0] > 0.10
                for c in cells.values()
            ),
            "note": (
                "N1 is reported over the grid because it depends on the alarms, "
                "and a single point would hide that. The primary cell is the "
                "lowest of the nine, so the headline is not the flattering one."
            ),
        },
        "by_threshold_cell": cells,
        "by_horizon_stratum": strata,
        "g3_gate": {
            "criterion": config["g3_gate"]["authorizes_g3_if"],
            "n1_estimate": n1["estimate"],
            "n1_wilson_lower": lower,
            "support_sufficient": estimable,
            "authorizes_g3": authorizes,
            "declared_before": config["g3_gate"]["declared_before"],
        },
        "per_week": [
            {**row, "recommendations": decision}
            for row, decision in zip(deduplicated, primary_decisions, strict=True)
        ],
        "not_called": config["n1"]["not_called"],
        "limits": config["limits"],
    }

    path = evidence.write_json_atomic(evidence.RESULTS / "02_discordance.json", payload)

    print()
    print("=" * 72)
    print(f"eligible origins              : {len(eligible)}")
    print(f"distinct target weeks         : {support}  (estimable: {estimable})")
    print(f"N1 = D(11,00)                 : {n1['estimate']}  "
          f"({n1['numerator']}/{n1['denominator']}), Wilson {n1['wilson_95']}")
    for name, block in simple.items():
        print(f"  {name:<14} {block['estimate']}")
    print(f"G3 authorized by the declared criterion : {authorizes}")
    print("=" * 72)
    print(f"wrote {path.relative_to(sources.ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
