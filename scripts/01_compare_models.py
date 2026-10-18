"""P2: M0 against one trainable candidate, on identical as-of origins.

What this is and is not. It is a **comparison**, not a selection: the promotion
rule — `delta_min`, disjoint four-week blocks, `n >= 12` — belongs to P4 and is
not applied here. M0 remains the provisional Champion throughout, and no result
in this file can move it.

The protocol, per origin `t`, identical for every candidate:

1. reconstruct the as-of state at `t` from one `/archive/` pull;
2. build features that only look backwards;
3. fit on rows whose target was **mature at `t`**, inside the declared universe;
4. forecast the week after the last one visible at `t`;
5. score later, against the same mature label, with the same fixed `s_dev`;
6. compare on **common** origins, and report every exclusion.

Two decisions registered in section 6 BIS of the G1-MP plan before any candidate
was scored, and both are enforced here rather than described:

* **Decision A.** The comparison universe is the scheduled Saturday calendar.
  Cuts displaced to a Sunday are operational evidence and are excluded by
  **calendar rule**; this script asserts that every origin is a Saturday instead
  of trusting that it is.
* **Decision B.** The nominal horizon stays +1, and losses are **stratified by
  publication lag**, because G1-A measured that lag ranging from 7 to 49 days.
  An average over cuts with different staleness is an average over different
  problems.

Development and selection are split at the same boundary that fixed `s_dev`, so
alpha and the F0/F1 recipe are chosen on the 2024-2025 season and never on the
periods they are then reported over.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pandas as pd

from revmon import evidence, sources
from revmon.evidence import Modality, RunManifest
from revmon.forecasting import (
    F0,
    F1,
    FEATURE_SETS,
    NAIVE,
    RIDGE,
    ForecastError,
    calibrate_scale,
    fit_and_forecast_ridge,
    forecast,
    scaled_loss,
)
from revmon.panel import as_of_view, fetch_triangle_as_of
from revmon.temporal import (
    SATURDAY,
    MaturityPolicy,
    ReplayMode,
    scheduled_cut,
)

DECLARED_IN = "P2 model comparison, declared 2026-10-18 before any candidate was scored"

#: The declared eligible universe. A regime change alters coverage without
#: altering the phenomenon, so rows from before it are a different population.
TRAIN_FROM = date(2024, 11, 1)

#: The same maturity policy and the same calibration window the G1 chain fixed,
#: so `s_dev` is identical across candidates and periods. Not recomputed here
#: with later data: a denominator that moves with the future can be fitted.
MATURITY = MaturityPolicy(days=45, declared_in=DECLARED_IN)
CALIBRATION = (date(2024, 11, 19), date(2025, 6, 30))

#: Development ends where the calibration window ends — the 2024-2025 season.
#: Alpha and the F0/F1 recipe are chosen here and nowhere else.
DEVELOPMENT_THROUGH = date(2025, 6, 30)

#: A small declared grid, searched only on development origins.
ALPHA_GRID: tuple[float, ...] = (0.1, 1.0, 10.0)

#: Supervised rows a trainable candidate needs before it may fit. Declared, not
#: tuned: an origin below it is reported as excluded, never filled in.
MIN_TRAIN_ROWS = 26

#: Decision B: the stratum boundary. 7 days is the nominal lag; anything longer
#: means the publication was late and the forecast used staler data.
NOMINAL_LAG_DAYS = 7


def candidate_cuts(first: date, last: date) -> list[date]:
    cursor = scheduled_cut(first)
    if cursor < first:
        cursor += timedelta(days=7)
    out = []
    while cursor <= last:
        out.append(cursor)
        cursor += timedelta(days=7)
    return out


def truth_by_week(triangle: pd.DataFrame, evaluated_at: date) -> dict[date, float]:
    """The mature label for each week, as seen now. One label for every candidate."""
    latest, _ = as_of_view(triangle, evaluated_at, ReplayMode.PUBLIC_REPLAY)
    labels: dict[date, float] = {}
    for row in latest.itertuples():
        week = pd.Timestamp(row.event_week_end).date()
        if MATURITY.is_eligible(week, evaluated_at):
            labels[week] = float(row.value)
    return labels


def forecasts_at(cut: date, state: pd.DataFrame, alpha: dict[str, float]) -> dict[str, dict]:
    """Every candidate's forecast at one origin, or why it has none."""
    out: dict[str, dict] = {}

    try:
        issued = forecast(state, cut, model=NAIVE)
        out[NAIVE] = {"forecast": issued.as_dict(), "excluded": None}
    except ForecastError as exc:
        out[NAIVE] = {"forecast": None, "excluded": str(exc)}

    for feature_set in FEATURE_SETS:
        name = f"{RIDGE}_{feature_set}"
        try:
            issued = fit_and_forecast_ridge(
                state,
                cut,
                feature_set=feature_set,
                policy=MATURITY,
                train_from=TRAIN_FROM,
                min_train_rows=MIN_TRAIN_ROWS,
                alpha=alpha[feature_set],
            )
            out[name] = {"forecast": issued.as_dict(), "excluded": None}
        except ForecastError as exc:
            out[name] = {"forecast": None, "excluded": str(exc)}
    return out


def score(rows: list[dict], model: str) -> dict:
    """Mean scaled loss for one candidate over the rows where it produced one."""
    losses = [r["loss"][model] for r in rows if r["loss"].get(model) is not None]
    if not losses:
        return {"n": 0, "mean_scaled_loss": None, "mean_absolute_error": None}
    errors = [r["abs_error"][model] for r in rows if r["abs_error"].get(model) is not None]
    return {
        "n": len(losses),
        "mean_scaled_loss": round(sum(losses) / len(losses), 6),
        "mean_absolute_error": round(sum(errors) / len(errors), 3),
    }


def choose_alpha(
    cuts: list[date],
    triangle: pd.DataFrame,
    labels: dict[date, float],
    scale,
) -> dict[str, dict]:
    """Alpha per feature set, on DEVELOPMENT origins only.

    Reported with the whole grid, not just the winner, so a reader can see how
    flat the choice was. A grid that barely separates is a grid whose winner
    should not be read as a finding.
    """
    chosen: dict[str, dict] = {}
    for feature_set in FEATURE_SETS:
        per_alpha: dict[str, dict] = {}
        for alpha in ALPHA_GRID:
            losses = []
            for cut in cuts:
                state, _ = as_of_view(triangle, cut, ReplayMode.PUBLIC_REPLAY)
                if state.empty:
                    continue
                try:
                    issued = fit_and_forecast_ridge(
                        state,
                        cut,
                        feature_set=feature_set,
                        policy=MATURITY,
                        train_from=TRAIN_FROM,
                        min_train_rows=MIN_TRAIN_ROWS,
                        alpha=alpha,
                    )
                except ForecastError:
                    continue
                target = date.fromisoformat(issued.target_week)
                if target in labels:
                    losses.append(scaled_loss(labels[target], issued.value, scale))
            per_alpha[str(alpha)] = {
                "n": len(losses),
                "mean_scaled_loss": (
                    round(sum(losses) / len(losses), 6) if losses else None
                ),
            }
        scored = {a: v for a, v in per_alpha.items() if v["mean_scaled_loss"] is not None}
        best = (
            min(scored, key=lambda a: scored[a]["mean_scaled_loss"]) if scored else None
        )
        chosen[feature_set] = {
            "grid": per_alpha,
            "chosen_alpha": float(best) if best else None,
            "chosen_on": "development origins only",
        }
    return chosen


def main() -> int:
    ran_at = datetime.now(UTC).date()
    evaluated_at = scheduled_cut(ran_at)

    manifest = RunManifest.start(
        decision_as_of=str(evaluated_at),
        modality=Modality.HISTORICAL_REPLAY,
        config={
            "declared_in": DECLARED_IN,
            "train_from": str(TRAIN_FROM),
            "maturity_days": MATURITY.days,
            "calibration_window": [str(CALIBRATION[0]), str(CALIBRATION[1])],
            "development_through": str(DEVELOPMENT_THROUGH),
            "alpha_grid": list(ALPHA_GRID),
            "min_train_rows": MIN_TRAIN_ROWS,
            "nominal_lag_days": NOMINAL_LAG_DAYS,
            "candidates": [NAIVE, f"{RIDGE}_{F0}", f"{RIDGE}_{F1}"],
            "promotion_rule": "not applied here; selection is P4",
        },
    )

    print("fetching the revision triangle once ...", flush=True)
    triangle, provenance = fetch_triangle_as_of(evaluated_at)
    if triangle.empty:
        print("the archive returned nothing; the comparison is NOT_VERIFIABLE")
        return 1

    reports = pd.to_datetime(triangle["source_report_date"]).dt.date
    labels = truth_by_week(triangle, evaluated_at)
    calibration_state, _ = as_of_view(triangle, CALIBRATION[1], ReplayMode.PUBLIC_REPLAY)
    scale = calibrate_scale(
        calibration_state,
        window_from=CALIBRATION[0],
        window_to=CALIBRATION[1],
        policy=MATURITY,
    )
    print(f"  s_dev = {scale.s_dev} over {scale.pairs} pairs", flush=True)

    cuts = [c for c in candidate_cuts(TRAIN_FROM, evaluated_at) if c >= min(reports)]
    # Decision A, enforced rather than described.
    off_calendar = [c for c in cuts if c.weekday() != SATURDAY]
    if off_calendar:
        print(f"origins off the scheduled calendar: {off_calendar}")
        return 1

    development = [c for c in cuts if c <= DEVELOPMENT_THROUGH]
    selection = [c for c in cuts if c > DEVELOPMENT_THROUGH]
    print(
        f"{len(cuts)} scheduled origins: {len(development)} development, "
        f"{len(selection)} selection",
        flush=True,
    )

    print("choosing alpha on development origins ...", flush=True)
    alpha_choice = choose_alpha(development, triangle, labels, scale)
    alpha = {
        fs: (alpha_choice[fs]["chosen_alpha"] or 1.0) for fs in FEATURE_SETS
    }
    for feature_set, info in alpha_choice.items():
        print(f"  {feature_set}: alpha = {info['chosen_alpha']}", flush=True)

    print("walking the selection origins ...", flush=True)
    rows: list[dict] = []
    for cut in selection:
        state, completeness = as_of_view(triangle, cut, ReplayMode.PUBLIC_REPLAY)
        if state.empty:
            continue
        last_visible = max(pd.to_datetime(state["event_week_end"]).dt.date)
        issued = forecasts_at(cut, state, alpha)
        target = last_visible + timedelta(weeks=1)
        if target not in labels:
            continue

        loss: dict[str, float | None] = {}
        abs_error: dict[str, float | None] = {}
        for name, record in issued.items():
            if record["forecast"] is None:
                loss[name] = None
                abs_error[name] = None
                continue
            predicted = record["forecast"]["y_pred"]
            abs_error[name] = round(abs(labels[target] - predicted), 3)
            loss[name] = round(scaled_loss(labels[target], predicted, scale), 6)

        rows.append({
            "cut": str(cut),
            "completeness": completeness.value,
            "last_visible_week": str(last_visible),
            "target_week": str(target),
            "publication_lag_days": (cut - last_visible).days,
            "y_mature": labels[target],
            "forecasts": {n: r["forecast"] for n, r in issued.items()},
            "excluded": {n: r["excluded"] for n, r in issued.items() if r["excluded"]},
            "loss": loss,
            "abs_error": abs_error,
        })

    candidates = [NAIVE, f"{RIDGE}_{F0}", f"{RIDGE}_{F1}"]
    common = [r for r in rows if all(r["loss"].get(c) is not None for c in candidates)]
    distinct = one_row_per_target_week(common)

    # Decision B: the same comparison, split by how stale the data was.
    strata = {
        "nominal_lag_7d": [r for r in common if r["publication_lag_days"] <= NOMINAL_LAG_DAYS],
        "delayed_publication": [
            r for r in common if r["publication_lag_days"] > NOMINAL_LAG_DAYS
        ],
    }

    payload = {
        "manifest": manifest.as_dict(),
        "provenance": provenance.as_dict() if provenance else None,
        "loss_scale": scale.as_dict(),
        "alpha_selection": alpha_choice,
        "universe": {
            "scheduled_origins": len(cuts),
            "development_origins": len(development),
            "selection_origins": len(selection),
            "scored_origins": len(rows),
            "common_origins": len(common),
            "all_cuts_on_the_scheduled_calendar": True,
            "decision_a": (
                "Sunday-displaced cuts are excluded by calendar rule, asserted above, "
                "never by looking at prediction error."
            ),
        },
        "training_feasibility_per_candidate": {
            candidate: {
                "origins_with_a_forecast": sum(
                    1 for r in rows if r["loss"].get(candidate) is not None
                ),
                "origins_excluded": sum(
                    1 for r in rows if candidate in r.get("excluded", {})
                ),
            }
            for candidate in candidates
        },
        # The headline, on one row per distinct target week. This is the
        # denominator the comparison is entitled to.
        "on_distinct_target_weeks": {c: score(distinct, c) for c in candidates},
        "paired_against_m0": paired(distinct, candidates),
        "support": {
            "common_origins": len(common),
            "distinct_target_weeks": len(distinct),
            "origins_above_distinct_weeks": len(common) - len(distinct),
            "rule": (
                "One row per target week, keeping the earliest origin. A stalled "
                "publication leaves the last visible week fixed while the calendar "
                "advances, so several origins forecast the same week from the same "
                "state; counting origins would weight that week once per origin."
            ),
            "repeated_target_weeks": {
                week: count
                for week, count in pd.Series(
                    [r["target_week"] for r in common]
                ).value_counts().items()
                if count > 1
            },
        },
        # Kept for inspection, and deliberately not the headline.
        "on_common_origins_undeduplicated": {c: score(common, c) for c in candidates},
        "by_publication_lag": {
            stratum: {
                "origins": len(subset),
                "distinct_target_weeks": len(one_row_per_target_week(subset)),
                "scores": {c: score(subset, c) for c in candidates},
            }
            for stratum, subset in strata.items()
        },
        "stratum_caveat": (
            "The delayed_publication stratum is one outage observed several times: "
            "every origin in it shares the same last visible week, the same target "
            "week and the same label. Its effective support is the number of distinct "
            "target weeks reported beside it, not the number of origins, and it "
            "supports no comparison between candidates."
        ),
        "alpha_caveat": (
            "Alpha was chosen on development origins from the declared grid, and the "
            "chosen value sits at the grid's edge, which usually means the grid is "
            "misplaced. It is reported as a limit rather than widened: extending the "
            "grid now would be choosing it after seeing these results. A wider grid "
            "has to be declared before a future run, not after this one."
        ),
        "origins": rows,
        "limits": (
            "A comparison, not a selection. The promotion rule (delta_min, disjoint "
            "four-week blocks, n >= 12) is P4 and is not applied here; M0 remains the "
            "provisional Champion. These weeks are correlated, so the counts are "
            "descriptive and support no significance or equivalence claim."
        ),
    }

    path = evidence.write_json_atomic(
        evidence.RESULTS / "01_model_comparison.json", payload
    )

    print()
    print("=" * 72)
    print(f"common origins         : {len(common)} of {len(rows)} scored")
    print(f"distinct target weeks  : {len(distinct)}  <- the denominator used")
    for candidate in candidates:
        info = payload["on_distinct_target_weeks"][candidate]
        print(f"  {candidate:16} n={info['n']:3}  "
              f"scaled loss {info['mean_scaled_loss']}  MAE {info['mean_absolute_error']}")
    print("paired against M0 (positive = the candidate wins):")
    for candidate, info in payload["paired_against_m0"].items():
        print(f"  {candidate:16} median {info['median_difference']:+.4f}  "
              f"wins {info['beats_m0']}, loses {info['loses_to_m0']}")
    print("by publication lag:")
    for stratum, info in payload["by_publication_lag"].items():
        print(f"  {stratum:22} origins={info['origins']}, "
              f"distinct weeks={info['distinct_target_weeks']}")
    print("=" * 72)
    print(f"wrote {path.relative_to(sources.ROOT)}")
    return 0


def one_row_per_target_week(common: list[dict]) -> list[dict]:
    """Collapse origins that forecast the **same** week to one row.

    Found by the stratification Decision B asked for, which is the point of
    stratifying. When a publication stalls, the last visible week stops moving
    while the calendar does not, so each successive Saturday origin forecasts
    *the same* target week from *the same* state. In this data a seven-week
    outage made `2025-09-27` the target of seven origins, with one label — so
    counting origins put `n` six above the number of distinct problems, and
    averaging over them would weight one week seven times.

    The kept row is the **earliest** origin for each target week: the first cut
    at which that week became forecastable under the +1 recipe. Chosen by
    calendar, like Decision A, never by which one scored better.
    """
    best: dict[str, dict] = {}
    for row in sorted(common, key=lambda r: r["cut"]):
        best.setdefault(row["target_week"], row)
    return sorted(best.values(), key=lambda r: r["cut"])


def paired(common: list[dict], candidates: list[str]) -> dict:
    """Per-origin differences against M0: median, and how often each side wins.

    Reported because a mean over a seasonal series is dominated by the peak
    weeks. The sign count does not depend on that scale, so it says something
    the mean cannot — and neither is a test.
    """
    out: dict[str, dict] = {}
    for candidate in candidates:
        if candidate == NAIVE:
            continue
        diffs = [r["loss"][NAIVE] - r["loss"][candidate] for r in common]
        if not diffs:
            out[candidate] = {"n": 0}
            continue
        out[candidate] = {
            "n": len(diffs),
            "median_difference": round(float(pd.Series(diffs).median()), 6),
            "mean_difference": round(sum(diffs) / len(diffs), 6),
            "beats_m0": sum(1 for d in diffs if d > 0),
            "ties_m0": sum(1 for d in diffs if d == 0),
            "loses_to_m0": sum(1 for d in diffs if d < 0),
        }
    return out


if __name__ == "__main__":
    raise SystemExit(main())
