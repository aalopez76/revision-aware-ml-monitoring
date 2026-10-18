"""G1-A: how many origins exist, measured, and what that number does not say.

Two quantities that must never be conflated, so they are written to separate
keys with separate names:

* **`temporally_eligible_origins`** — cuts where an as-of state exists, a
  forecast is producible from it, and the target label has matured by the
  evaluation date. Measurable today, from the data that exists.
* **`training_feasibility_per_candidate`** — whether Ridge, LightGBM or
  AutoGluon can actually be fitted on those origins. **Not measurable here**: the
  models do not exist yet. Every entry is `pending_P2`, and reporting the first
  number as if it were the second would be attributing a result to a model that
  was never trained.

The ceiling G0 measured was weekly national cuts of *version history*. This asks
the narrower question that a model comparison actually needs, and the answer is
smaller than the ceiling and larger than the "40-60 folds" that an earlier
review guessed at. That guess was never measured and is not used.

Cost: one `/archive/` request. Every cut is then derived locally, which G0
licensed by measuring that the reconstruction reproduces a direct snapshot
exactly at three test cuts.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pandas as pd

from revmon import evidence, sources
from revmon.evidence import Modality, RunManifest
from revmon.panel import as_of_view, fetch_triangle_as_of
from revmon.temporal import (
    SENSITIVITY_WINDOWS_DAYS,
    MaturityPolicy,
    ReplayMode,
    scheduled_cut,
)

DECLARED_IN = "G1-A support measurement, P0 of the G1-MP plan, 2026-10-18"

#: The eligible universe, declared in G0 before results were seen: the mandate
#: resumed on this date, and the archive begins 18 days later, so the voluntary
#: period has no version history to contaminate anything.
UNIVERSE_FROM = date(2024, 11, 1)

#: A declared floor on visible history, not a measurement of any model's need.
#: It exists so "a forecast is producible" means something checkable; which
#: models need more than this is a P2 question.
MIN_VISIBLE_WEEKS = 8


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


def main() -> int:
    ran_at = datetime.now(UTC).date()
    evaluated_at = scheduled_cut(ran_at)

    manifest = RunManifest.start(
        decision_as_of=str(evaluated_at),
        modality=Modality.HISTORICAL_REPLAY,
        config={
            "universe_from": str(UNIVERSE_FROM),
            "min_visible_weeks": MIN_VISIBLE_WEEKS,
            "maturity_grid_days": list(SENSITIVITY_WINDOWS_DAYS),
            "declared_in": DECLARED_IN,
        },
    )

    print("fetching the revision triangle once ...", flush=True)
    triangle, provenance = fetch_triangle_as_of(evaluated_at)
    if triangle.empty:
        print("the archive returned nothing; support is NOT_VERIFIABLE")
        return 1

    reports = pd.to_datetime(triangle["source_report_date"]).dt.date
    weeks = pd.to_datetime(triangle["event_week_end"]).dt.date
    archive_from = min(reports)

    cuts = [c for c in candidate_cuts(UNIVERSE_FROM, evaluated_at) if c >= archive_from]
    print(f"deriving {len(cuts)} scheduled cuts locally ...", flush=True)

    rows = []
    for cut in cuts:
        state, completeness = as_of_view(triangle, cut, ReplayMode.PUBLIC_REPLAY)
        if state.empty:
            rows.append((cut, 0, None, None, completeness.value))
            continue
        visible = pd.to_datetime(state["event_week_end"]).dt.date
        last_week = max(visible)
        rows.append((
            cut,
            len(state),
            last_week,
            last_week + timedelta(weeks=1),
            completeness.value,
        ))

    frame = pd.DataFrame(
        rows,
        columns=["cut", "visible_weeks", "last_visible_week", "target_week", "completeness"],
    )
    producible = frame[
        (frame["visible_weeks"] >= MIN_VISIBLE_WEEKS) & frame["target_week"].notna()
    ]
    lags = (producible["cut"] - producible["last_visible_week"]).apply(lambda d: d.days)

    eligible: dict[str, dict] = {}
    for days in SENSITIVITY_WINDOWS_DAYS:
        policy = MaturityPolicy(days=days, declared_in=DECLARED_IN)
        mature = producible[
            [policy.is_eligible(t, evaluated_at) for t in producible["target_week"]]
        ]
        eligible[str(days)] = {
            "origins": int(len(mature)),
            "first_cut": str(mature["cut"].min()) if len(mature) else None,
            "last_cut": str(mature["cut"].max()) if len(mature) else None,
        }

    declared = str(SENSITIVITY_WINDOWS_DAYS[0])
    payload = {
        "manifest": manifest.as_dict(),
        "provenance": provenance.as_dict() if provenance else None,
        "universe": {
            "declared_from": str(UNIVERSE_FROM),
            "archive_begins": str(archive_from),
            "event_week_first": str(min(weeks)),
            "event_week_last": str(max(weeks)),
            "evaluated_at": str(evaluated_at),
            "ran_at": str(ran_at),
        },
        "temporally_eligible_origins": {
            "candidate_scheduled_cuts": int(len(frame)),
            "cuts_with_state": int((frame["visible_weeks"] > 0).sum()),
            "cuts_forecast_producible": int(len(producible)),
            "min_visible_weeks": MIN_VISIBLE_WEEKS,
            "by_maturity_days": eligible,
            "declared_policy_days": int(SENSITIVITY_WINDOWS_DAYS[0]),
            "declared_policy_origins": eligible[declared]["origins"],
            "completeness_counts": frame["completeness"].value_counts().to_dict(),
        },
        "publication_lag_days": {
            "median": int(lags.median()),
            "min": int(lags.min()),
            "max": int(lags.max()),
            "note": (
                "Days from the cut to the last event week visible at it. The spread "
                "is why the effective horizon varies even though the recipe is fixed "
                "at +1, and why a loss averaged across cuts mixes horizons. "
                "Stratification is a G2 decision, declared before it is used."
            ),
        },
        "training_feasibility_per_candidate": {
            # Not measurable in this script and never guessed here: it depends on
            # models that this script knows nothing about. P2 measures it per
            # candidate, with its exclusions, in 01_model_comparison.json.
            candidate: "not measurable here; see 01_model_comparison.json"
            for candidate in ("M0", "M1", "M2", "M3a", "M3b")
        },
        "limits": (
            "These are origins eligible by date, maturity and visible history only. "
            "Whether any candidate can be fitted on them is not measured here and is "
            "decided in P2. No folds figure is estimated or implied."
        ),
    }

    path = evidence.write_json_atomic(
        evidence.RESULTS / "01_modeling_support.json", payload
    )

    print()
    print("=" * 72)
    print(f"candidate scheduled cuts      : {len(frame)}")
    print(f"forecast producible           : {len(producible)}")
    for days, info in eligible.items():
        print(f"eligible origins @ {days:>3} days   : {info['origins']}")
    print(f"publication lag (days)        : median {int(lags.median())}, "
          f"min {int(lags.min())}, max {int(lags.max())}")
    print("training feasibility          : not measurable here; P2 measures it")
    print("=" * 72)
    print(f"wrote {path.relative_to(sources.ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
