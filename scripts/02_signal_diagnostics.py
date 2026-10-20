"""G2-A: what the two information signals actually look like, before any threshold.

G2 crosses two factors of information, R (revision history) and C (coverage
indicators). The crossing is only meaningful if each factor can take more than
one value, and the G1 chain's own artefact says they could not:

* `revision_share` was 1.0 at all 14 replay cuts and at the observed run, and
* `coverage_drop` was `null` at all 14 replay cuts, because the replay loop was
  never handed a coverage state.

A constant factor crossed with an absent one is not a 2x2. So this script
measures the distribution of both signals, under both anchorings, over the
development origins -- and **declares no threshold**. Choosing one is the next
step and it belongs in versioned config; choosing it inside the script that
measured the distribution is how a threshold stops being predeclared.

What it measures, and one thing it deliberately does not:

* **Both signals under two anchorings.** `series_edge` is what G1 used: the
  window ends at the newest event week present. `matured_window` ends at the
  newest week whose label has matured at the cut, which puts R and C at the same
  lag. The difference between the two columns is the defect, quantified.
* **Revision rate by publication lag.** Whether the edge is structurally
  restated, and where that stops. This is the measurement that would justify any
  anchoring, and buckets are cut at 45/60/90 days so it also speaks to the
  pre-declared maturity grid.
* **The size of the restatements, not only their count.** Added after the first
  run measured that the revised *share* is 1.0 in every lag bucket, out to past
  180 days: this source restates every value in every publication, so a share
  of revised pairs is saturated and re-anchoring it cannot help. A saturated
  signal is reported as saturated, and the magnitude is then measured so that
  the config step has something with spread to choose from. `config/g2_signals.json`
  then adopted it, which is why `revision_magnitude` now lives in
  `revmon.monitoring` and this script imports it rather than defining it.
* **Whether the PERFORMANCE branch is reachable.** The G1 replay exited early at
  8 of 14 cuts with zero mature labels, so a discordance computed there would
  have measured the precedence table's early exits. Counted from the calendar
  alone -- prior origins whose target had matured -- because counting it from
  stored predictions would need predictions this script must not issue.
* **No threshold, and no cut after development.** Both pulls are bounded at
  `DEVELOPMENT_THROUGH` server-side, so the script cannot see a later
  publication even by filtering wrongly. That is a structural guarantee rather
  than a promise in a docstring.

Cost: two `/archive/` requests. Every cut is then derived locally, which G0
licensed by measuring that the reconstruction reproduces a direct snapshot
exactly at three test cuts.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import numpy as np
import pandas as pd

from revmon import evidence, sources
from revmon.evidence import Modality, RunManifest
from revmon.monitoring import (
    coverage_drop,
    relative_revisions,
    revision_magnitude,
    revision_share,
)
from revmon.panel import as_of_view, fetch_triangle_as_of, visible_triangle
from revmon.temporal import (
    SATURDAY,
    Completeness,
    MaturityPolicy,
    ReplayMode,
    scheduled_cut,
)

DECLARED_IN = "G2-A signal diagnostics, 2026-10-19, before any G2 threshold was declared"

#: The declared eligible universe, unchanged since G0.
UNIVERSE_FROM = date(2024, 11, 1)

#: The same policy the whole chain uses. Not re-chosen here: this script reports
#: a distribution, and a script that could move the maturity rule while
#: measuring the signal could fit the signal.
MATURITY = MaturityPolicy(days=45, declared_in=DECLARED_IN)

#: Development ends where `s_dev` and P2's alpha search ended -- the 2024-2025
#: season. Both pulls are bounded here, so nothing later is fetched at all.
DEVELOPMENT_THROUGH = date(2025, 6, 30)

#: The G1 window lengths, carried over unchanged. This script is about where a
#: window **ends**, not how long it is; changing both at once would make the
#: comparison uninterpretable.
REVISION_LOOKBACK_WEEKS = 8
COVERAGE_LOOKBACK_WEEKS = 4

#: Upper edges in days, in the sense of `lag_days`: publication date minus event
#: week. 45, 60 and 90 are the pre-declared maturity grid, so the same table
#: reports what each maturity choice would be buying.
LAG_BUCKET_EDGES = (7, 14, 21, 28, 45, 60, 90, 180)

#: Grids over which the *distribution* is reported. Reporting the share of cuts
#: above each candidate value is describing the signal; picking one of them is
#: the next step, in config, and not here.
REVISION_THRESHOLD_GRID = (0.0, 0.05, 0.10, 0.25, 0.50, 0.75, 0.99)
MAGNITUDE_THRESHOLD_GRID = (0.0, 0.001, 0.005, 0.01, 0.02, 0.05, 0.10)
COVERAGE_THRESHOLD_GRID = (0.0, 0.5, 1.0, 2.0, 5.0, 10.0)
MIN_MATURE_GRID = (1, 2, 4, 8, 12, 20)


def candidate_cuts(first: date, last: date) -> list[date]:
    """Every scheduled weekly cut in the window, anchored to the source's Saturday."""
    cursor = scheduled_cut(first)
    if cursor < first:
        cursor += timedelta(days=7)
    out = []
    while cursor <= last:
        out.append(cursor)
        cursor += timedelta(days=7)
    return out


def matured_anchor(weeks: list[date], cut: date, policy: MaturityPolicy) -> date | None:
    """The newest event week whose label has matured at the cut.

    `None` when none has. That is a real state early in the archive and it is
    reported as such rather than falling back to the series edge, which is the
    anchoring this script exists to contrast.
    """
    mature = [w for w in weeks if policy.is_eligible(w, cut)]
    return max(mature) if mature else None


def describe(values: list[float | None]) -> dict:
    """The distribution, plus whether the signal is constant -- which is the point."""
    present = [v for v in values if v is not None]
    if not present:
        return {
            "n": len(values),
            "n_missing": len(values),
            "constant": None,
            "note": "the signal was never computable at any cut",
        }
    array = np.asarray(present, dtype=float)
    return {
        "n": len(values),
        "n_missing": int(len(values) - len(present)),
        "min": round(float(array.min()), 6),
        "p10": round(float(np.quantile(array, 0.10)), 6),
        "median": round(float(np.quantile(array, 0.50)), 6),
        "p90": round(float(np.quantile(array, 0.90)), 6),
        "max": round(float(array.max()), 6),
        "distinct_values": int(len(np.unique(np.round(array, 6)))),
        "constant": bool(len(np.unique(np.round(array, 6))) == 1),
    }


def share_above(values: list[float | None], grid: tuple[float, ...]) -> dict:
    """Share of cuts where the signal exceeds each candidate value.

    Strictly above, because that is what the rule table does. A cut where the
    signal is missing is counted in the denominator and never as an alarm: an
    absent signal is not a quiet one.
    """
    out = {}
    for threshold in grid:
        fired = sum(1 for v in values if v is not None and v > threshold)
        out[str(threshold)] = {
            "cuts_above": fired,
            "share": round(fired / len(values), 6) if values else None,
        }
    return out


def _bucket(flags: pd.Series, magnitudes: pd.Series) -> dict:
    total = int(len(flags))
    bucket = {
        "pairs": total,
        "revised": int(flags.sum()),
        "revised_share": round(float(flags.mean()), 6) if total else None,
    }
    if len(magnitudes):
        array = magnitudes.to_numpy(dtype=float)
        bucket["abs_relative_revision"] = {
            "median": round(float(np.quantile(array, 0.50)), 6),
            "p90": round(float(np.quantile(array, 0.90)), 6),
            "max": round(float(array.max()), 6),
            "pairs_with_nonzero_base": int(len(array)),
        }
    return bucket


def revision_by_lag(triangle: pd.DataFrame) -> dict:
    """Revised share of comparable pairs, bucketed by how late the version came.

    A property of the triangle rather than of any cut: it answers whether the
    newest weeks are restated by construction, and where that stops. If the
    early buckets are near 1 and the late ones near 0, then an edge-anchored
    revision signal is measuring the calendar.
    """
    later = triangle[~triangle["is_first_release"].astype(bool)].copy()
    if later.empty:
        return {"note": "no comparable pairs in the development triangle"}
    lags = pd.to_numeric(later["lag_days"], errors="coerce")
    revised = later["revised"].astype(bool)
    relative = relative_revisions(later)

    buckets: dict[str, dict] = {}
    previous = -1
    for edge in LAG_BUCKET_EDGES:
        inside = (lags > previous) & (lags <= edge)
        buckets[f"{previous + 1}-{edge}"] = _bucket(
            revised[inside], relative[relative.index.isin(later.index[inside])]
        )
        previous = edge
    tail = lags > LAG_BUCKET_EDGES[-1]
    buckets[f">{LAG_BUCKET_EDGES[-1]}"] = _bucket(
        revised[tail], relative[relative.index.isin(later.index[tail])]
    )

    # The headline is a measured key rather than a sum a reader has to do over
    # nine buckets: whether the revised *share* discriminates anything at all.
    return {
        "all_comparable_pairs": {
            **_bucket(revised, relative),
            "note": (
                "Pairs where the key appeared in two successive publications, "
                "which is the denominator G0 measured to be the right one. A "
                "revised share of 1.0 means the share cannot discriminate: it is "
                "saturated, and no window or anchor changes that."
            ),
        },
        "by_lag_days": buckets,
    }


def main() -> int:
    ran_at = datetime.now(UTC).date()

    manifest = RunManifest.start(
        decision_as_of=str(DEVELOPMENT_THROUGH),
        modality=Modality.HISTORICAL_REPLAY,
        config={
            "universe_from": str(UNIVERSE_FROM),
            "development_through": str(DEVELOPMENT_THROUGH),
            "maturity_days": MATURITY.days,
            "revision_lookback_weeks": REVISION_LOOKBACK_WEEKS,
            "coverage_lookback_weeks": COVERAGE_LOOKBACK_WEEKS,
            "declared_in": DECLARED_IN,
        },
    )

    print("fetching the target triangle once, bounded at development ...", flush=True)
    target, target_prov = fetch_triangle_as_of(DEVELOPMENT_THROUGH)
    if target.empty:
        print("the archive returned nothing; the diagnostics are NOT_VERIFIABLE")
        return 1

    print("fetching the coverage triangle once ...", flush=True)
    coverage, coverage_prov = fetch_triangle_as_of(
        DEVELOPMENT_THROUGH, signal=sources.COVERAGE_PCT_SIGNAL
    )

    reports = pd.to_datetime(target["source_report_date"]).dt.date
    archive_from = min(reports)
    cuts = [c for c in candidate_cuts(UNIVERSE_FROM, DEVELOPMENT_THROUGH) if c >= archive_from]
    assert all(c.weekday() == SATURDAY for c in cuts), "Decision A: every origin is a Saturday"
    print(f"deriving {len(cuts)} development cuts locally ...", flush=True)

    # First pass: what each origin would have forecast. Needed before the second
    # pass can count how many earlier origins had a matured target.
    targets: dict[date, date] = {}
    for cut in cuts:
        state, status = as_of_view(target, cut, ReplayMode.PUBLIC_REPLAY)
        if status is Completeness.COMPLETE and not state.empty:
            last_week = max(pd.to_datetime(state["event_week_end"]).dt.date)
            targets[cut] = last_week + timedelta(weeks=1)

    rows = []
    for cut in cuts:
        state, status = as_of_view(target, cut, ReplayMode.PUBLIC_REPLAY)
        triangle_at_cut = visible_triangle(target, cut, ReplayMode.PUBLIC_REPLAY)
        cover_state, _ = as_of_view(coverage, cut, ReplayMode.PUBLIC_REPLAY)

        weeks = (
            sorted(pd.to_datetime(state["event_week_end"]).dt.date) if not state.empty else []
        )
        anchor = matured_anchor(weeks, cut, MATURITY)
        magnitude_mean, magnitude_max = revision_magnitude(
            triangle_at_cut, REVISION_LOOKBACK_WEEKS, anchor_week=anchor
        )
        scorable = sum(
            1
            for origin, week in targets.items()
            if origin < cut and MATURITY.is_eligible(week, cut)
        )

        rows.append({
            "cut": str(cut),
            "completeness": status.value,
            "visible_weeks": int(len(state)),
            "last_visible_week": str(max(weeks)) if weeks else None,
            "publication_lag_days": (cut - max(weeks)).days if weeks else None,
            "matured_anchor_week": str(anchor) if anchor else None,
            "r_series_edge": revision_share(triangle_at_cut, REVISION_LOOKBACK_WEEKS),
            "r_matured_window": (
                revision_share(triangle_at_cut, REVISION_LOOKBACK_WEEKS, anchor_week=anchor)
                if anchor
                else None
            ),
            "r_magnitude_mean": magnitude_mean,
            "r_magnitude_max": magnitude_max,
            "c_series_edge": coverage_drop(cover_state, COVERAGE_LOOKBACK_WEEKS),
            "c_matured_window": (
                coverage_drop(cover_state, COVERAGE_LOOKBACK_WEEKS, anchor_week=anchor)
                if anchor
                else None
            ),
            "scorable_prior_origins": scorable,
        })

    def column(name: str) -> list:
        return [r[name] for r in rows]

    signals = {}
    for name, grid in (
        ("r_series_edge", REVISION_THRESHOLD_GRID),
        ("r_matured_window", REVISION_THRESHOLD_GRID),
        ("r_magnitude_mean", MAGNITUDE_THRESHOLD_GRID),
        ("r_magnitude_max", MAGNITUDE_THRESHOLD_GRID),
        ("c_series_edge", COVERAGE_THRESHOLD_GRID),
        ("c_matured_window", COVERAGE_THRESHOLD_GRID),
    ):
        signals[name] = {
            "distribution": describe(column(name)),
            "share_above": share_above(column(name), grid),
        }

    scorable_column = column("scorable_prior_origins")
    reachable = {
        str(minimum): {
            "cuts_reaching_performance": sum(1 for s in scorable_column if s >= minimum),
            "share": round(
                sum(1 for s in scorable_column if s >= minimum) / len(scorable_column), 6
            ),
        }
        for minimum in MIN_MATURE_GRID
    }

    payload = {
        "manifest": manifest.as_dict(),
        "provenance": {
            "target": target_prov.as_dict() if target_prov else None,
            "coverage": coverage_prov.as_dict() if coverage_prov else None,
        },
        "window": {
            "declared_from": str(UNIVERSE_FROM),
            "archive_begins": str(archive_from),
            "development_through": str(DEVELOPMENT_THROUGH),
            "ran_at": str(ran_at),
            "development_cuts": len(cuts),
            "coverage_rows": int(len(coverage)),
            "bounded_server_side": (
                "Both pulls bound report_time at development_through, so a later "
                "publication was never fetched. Nothing here looks past it."
            ),
        },
        "signals": signals,
        "revision_by_publication_lag": revision_by_lag(target),
        "performance_branch_reachability": {
            "by_min_mature_labels": reachable,
            "scorable_prior_origins": describe([float(s) for s in scorable_column]),
            "note": (
                "Counted from the calendar: earlier scheduled origins whose target "
                "week had matured at the cut. It is the ceiling on what a rolling "
                "evaluation could score, not a count of stored predictions."
            ),
        },
        "per_cut": rows,
        "declares_no_threshold": (
            "This artefact reports distributions only. The anchoring, the N1 "
            "threshold grid and the minimum support are declared in versioned "
            "config as the next step, and a threshold chosen inside the script "
            "that measured the distribution would not be predeclared."
        ),
        "limits": (
            "Development origins only, and the two signals are described, not "
            "validated: a signal with spread is not thereby informative about the "
            "model. Nothing here is a discordance, and no recommendation was "
            "emitted at any cut."
        ),
    }

    path = evidence.write_json_atomic(
        evidence.RESULTS / "02_signal_diagnostics.json", payload
    )

    print()
    print("=" * 72)
    print(f"development cuts              : {len(cuts)}")
    for name, block in signals.items():
        dist = block["distribution"]
        if "median" in dist:
            print(
                f"{name:<18} median {dist['median']:>10.4f}  "
                f"distinct {dist['distinct_values']:>3}  "
                f"missing {dist['n_missing']:>3}  "
                f"constant {dist['constant']}"
            )
        else:
            print(f"{name:<18} never computable at any cut")
    print(
        f"reaches PERFORMANCE @4 labels : "
        f"{reachable['4']['cuts_reaching_performance']}/{len(cuts)}"
    )
    print("=" * 72)
    print(f"wrote {path.relative_to(sources.ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
