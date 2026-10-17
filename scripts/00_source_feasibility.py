"""G0: measure what the sources actually guarantee. Do not assume anything.

This is the first measurement the project makes, and its job is to decide
whether the central experiment is feasible at all — not to produce a headline.
Every probe records its own provenance (`request_url`, `observed_at`), every
finding is written to `reports/results/00_source_feasibility.json`, and a probe
that fails records the failure instead of degrading into a guess.

The verdict is one of PROCEED / REDUCE / STOP_SOURCE, against criteria declared
here, in code, before the numbers exist.

What it answers, in the order of the specification:

  G0.1  authentication against a real v5 path
  G0.2  the first and last `reference_time` and `report_time` recoverable
  G0.3  `/archive/` semantics, and whether a snapshot reconstructs from it
  G0.4  the publication calendar, and the coverage signals by name
  G0.5  alignment against the FluSight hub's git history
  G0.6  how many weekly national cuts the measured history can support
  G0.7  what the queries cost
"""

from __future__ import annotations

import time
from datetime import UTC, date, datetime

import pandas as pd

from revmon import sources

# --- declared before the numbers exist -------------------------------------

#: Bounded window for the semantics probe. A full-history archive pull for one
#: geography could be tens of thousands of rows, and a bounded window answers
#: the question just as well while keeping the response small.
SEMANTICS_WINDOW = (date(2025, 9, 1), date(2026, 10, 10))

#: Cuts at which a reconstruction from `/archive/` is compared against a direct
#: `/snapshot/`. Three, spread across the measured version history.
RECONSTRUCTION_CUTS = ("2025-02-05", "2025-10-15", "2026-06-10")

#: Verdict thresholds, declared. The ceiling is the number of weekly national
#: cuts the version history can possibly support, before eligibility prunes it.
MIN_CUTS_PROCEED = 60
MIN_CUTS_REDUCE = 20

#: The identity of an observation, minus the publication clock. Taken from the
#: source's own `key_columns`, which includes `fill_method`: two rows differing
#: only in that field are not a revision of one another.
STATE_KEY = ["signal", "geo_type", "geo_value", "fill_method", "reference_time"]


class Budget:
    """Counts requests and wall time, so G0.7 is measured and not estimated."""

    def __init__(self) -> None:
        self.requests = 0
        self.started = time.monotonic()

    def spend(self, n: int = 1) -> None:
        self.requests += n

    def report(self) -> dict:
        return {
            "requests_issued": self.requests,
            "wall_seconds": round(time.monotonic() - self.started, 1),
        }


def probe(name: str, fn, budget: Budget, *, cost: int = 1) -> dict:
    """Run one probe, and record a failure as a finding rather than crashing."""
    print(f"[{name}] ...", flush=True)
    try:
        budget.spend(cost)
        result = fn()
        result["status"] = "ok"
    except Exception as exc:  # noqa: BLE001 - a failed probe is a finding
        result = {"status": "failed", "error_type": type(exc).__name__, "error": str(exc)[:500]}
        print(f"[{name}] FALLO: {type(exc).__name__}: {str(exc)[:200]}", flush=True)
    return result


# --- G0.1, G0.2, G0.4 (signals): source metadata ---------------------------


def probe_metadata() -> dict:
    meta = sources.v5_metadata()
    signals = list(meta["signals"])
    wanted = {
        "target": sources.TARGET_SIGNAL,
        "coverage_count": sources.COVERAGE_COUNT_SIGNAL,
        "coverage_pct": sources.COVERAGE_PCT_SIGNAL,
    }
    return {
        "api_key_configured": sources.api_key_present(),
        "reference_time_range": meta["reference_time_range"],
        "report_time_range": meta["report_time_range"],
        "key_columns": list(meta["key_columns"]),
        "extra_key_columns": list(meta["extra_key_columns"]),
        "value_columns": list(meta["value_columns"]),
        "geo_types": sorted(meta["geo_types"]),
        "signals_total": len(signals),
        "signals_present": {role: (name in signals) for role, name in wanted.items()},
    }


# --- G0.4: the publication calendar ----------------------------------------


def probe_calendar() -> dict:
    times, prov = sources.v5_report_times()
    dates = sorted({t[:10] for t in times})
    stamps = pd.to_datetime(pd.Series(dates))
    gaps = stamps.diff().dt.days.dropna()
    per_week = stamps.dt.strftime("%G-W%V").value_counts()
    return {
        "provenance": prov.as_dict(),
        # The full calendar is kept in the artefact on purpose: it is the only
        # honest basis for the revision-rate denominator, so it is evidence and
        # not a detail.
        "dates": dates,
        "publication_dates": len(dates),
        "first": dates[0],
        "last": dates[-1],
        "iso_weeks_covered": int(per_week.size),
        "publications_per_iso_week": {
            "min": int(per_week.min()),
            "median": float(per_week.median()),
            "max": int(per_week.max()),
        },
        "days_between_publications": {
            "min": int(gaps.min()),
            "median": float(gaps.median()),
            "max": int(gaps.max()),
        },
        # The old design treated one hub commit as one publication. If the
        # source publishes more often than weekly, that proxy undercounts, and
        # the revision rate built on it is a looser lower bound than stated.
        "weekly_cadence_assumption_holds": bool(per_week.max() <= 1),
    }


# --- G0.3: what /archive/ actually returns ---------------------------------


def probe_archive_semantics(calendar: dict) -> dict:
    start, end = SEMANTICS_WINDOW
    # Both axes are bounded to the same dates on purpose. Bounding only
    # `reference_time` and then counting distinct `report_time` values would
    # compare a publication count against an event window — two different axes,
    # and a number that looks like a ratio while meaning nothing.
    frame, prov = sources.v5_archive(
        signals=sources.TARGET_SIGNAL,
        reference_time=sources.date_range(start, end),
        report_time=sources.date_range(start, end),
    )
    frame = frame.copy()
    rows_per_key = frame.groupby(STATE_KEY, dropna=False).size()
    archive_report_times = sorted({str(t)[:10] for t in frame["report_time"].unique()})

    # Publications that fall inside the window. A "every version per
    # report_time" reading would have to produce roughly this many rows for a
    # key that existed throughout; a diffs reading produces far fewer.
    calendar_in_window = [
        d for d in calendar.get("dates", []) if str(start) <= d <= str(end)
    ]

    median_rows = float(rows_per_key.median()) if len(rows_per_key) else 0.0
    if not len(rows_per_key):
        verdict = "indeterminate"
    elif median_rows <= 1.5:
        verdict = "diffs_only"
    else:
        verdict = "multiple_versions_per_key"

    return {
        "provenance": prov.as_dict(),
        "window": {"from": str(start), "to": str(end)},
        "rows": int(len(frame)),
        "distinct_keys": int(len(rows_per_key)),
        "rows_per_key": {
            "min": int(rows_per_key.min()) if len(rows_per_key) else 0,
            "median": median_rows,
            "max": int(rows_per_key.max()) if len(rows_per_key) else 0,
        },
        "distinct_report_times_in_archive": len(archive_report_times),
        "calendar_publications_in_window": len(calendar_in_window),
        # Comparable now that both axes share the window: how much of the
        # publication calendar actually carried a row for this signal.
        "share_of_publications_present": (
            round(len(archive_report_times) / len(calendar_in_window), 3)
            if calendar_in_window
            else None
        ),
        "median_versions_per_key_vs_publications": (
            round(median_rows / len(calendar_in_window), 3) if calendar_in_window else None
        ),
        # The documentation and the client's docstring disagree about this.
        # Whatever this says, it is a measurement and it supersedes both.
        "semantics_verdict": verdict,
        "note": (
            "A median of ~1 row per key means unchanged republications are absent, "
            "so the revision-rate denominator must come from the publication "
            "calendar and not from these rows."
        ),
    }


def probe_reconstruction() -> dict:
    """Reconstruct each cut from /archive/ and compare against /snapshot/."""
    comparisons = []
    for cut in RECONSTRUCTION_CUTS:
        direct, prov_snap = sources.v5_snapshot(
            signals=sources.TARGET_SIGNAL, snapshot_date=cut
        )
        history, prov_arch = sources.v5_archive(
            signals=sources.TARGET_SIGNAL,
            report_time=sources.date_range("2024-11-01", cut),
        )
        rebuilt = (
            history.sort_values("report_time")
            .groupby(STATE_KEY, as_index=False, dropna=False)
            .last()
        )

        on = ["reference_time"]
        left = direct[[*on, "value"]].rename(columns={"value": "snapshot"})
        right = rebuilt[[*on, "value"]].rename(columns={"value": "rebuilt"})
        merged = left.merge(right, on=on, how="outer", indicator=True)
        both = merged[merged["_merge"] == "both"]
        mismatched = both[both["snapshot"] != both["rebuilt"]]

        comparisons.append(
            {
                "cut": cut,
                "snapshot_rows": int(len(direct)),
                "rebuilt_rows": int(len(rebuilt)),
                "keys_only_in_snapshot": int((merged["_merge"] == "left_only").sum()),
                "keys_only_in_rebuilt": int((merged["_merge"] == "right_only").sum()),
                "value_mismatches": int(len(mismatched)),
                "reconstructs_exactly": bool(
                    len(mismatched) == 0
                    and (merged["_merge"] != "both").sum() == 0
                ),
                "provenance": [prov_snap.as_dict(), prov_arch.as_dict()],
            }
        )

    return {
        "cuts": comparisons,
        "all_cuts_reconstruct": all(c["reconstructs_exactly"] for c in comparisons),
    }


# --- G0.4: the coverage signals carry data ---------------------------------


def probe_coverage_signals() -> dict:
    out = {}
    for role, signal in (
        ("coverage_count", sources.COVERAGE_COUNT_SIGNAL),
        ("coverage_pct", sources.COVERAGE_PCT_SIGNAL),
    ):
        frame, prov = sources.v5_snapshot(signals=signal)
        weeks = pd.to_datetime(frame["reference_time"])
        out[role] = {
            "signal": signal,
            "rows": int(len(frame)),
            "first_reference_time": str(weeks.min().date()) if len(frame) else None,
            "last_reference_time": str(weeks.max().date()) if len(frame) else None,
            "nulls": int(frame["value"].isna().sum()),
            "provenance": prov.as_dict(),
        }
    return out


# --- G0.5: the second reconstruction --------------------------------------


def probe_hub_alignment() -> dict:
    hub_series, prov = sources.hub_national_series()
    v5, prov_v5 = sources.v5_snapshot(signals=sources.TARGET_SIGNAL)

    v5_series = (
        v5.assign(week=pd.to_datetime(v5["reference_time"]).dt.date)[["week", "value"]]
        .rename(columns={"value": "v5_value"})
        .drop_duplicates("week")
    )
    merged = hub_series.merge(v5_series, on="week", how="inner")
    disagree = merged[merged["hub_value"] != merged["v5_value"]]

    return {
        "hub_national_rows": int(len(hub_series)),
        "v5_national_rows": int(len(v5_series)),
        "overlapping_weeks": int(len(merged)),
        "agreeing_weeks": int(len(merged) - len(disagree)),
        "disagreeing_weeks": int(len(disagree)),
        "example_disagreements": [
            {"week": str(r.week), "hub": float(r.hub_value), "v5": float(r.v5_value)}
            for r in disagree.head(5).itertuples()
        ],
        "aligned": bool(len(merged) > 0),
        "note": (
            "Two publication channels, not two independent measurements. A "
            "disagreement is reported, not corrected, and a hub commit is not "
            "the instant a value became available from NHSN."
        ),
        "provenance": [prov.as_dict(), prov_v5.as_dict()],
    }


# --- G0.6: the support ceiling --------------------------------------------


def support_ceiling(metadata: dict) -> dict:
    if metadata.get("status") != "ok":
        return {"status": "unavailable"}
    rep = metadata["report_time_range"]
    ref = metadata["reference_time_range"]
    # The source names these `first` and `latest`. Read exactly, so that a
    # changed shape fails here instead of producing a plausible wrong number.
    rep_first, rep_last = pd.Timestamp(rep["first"]).date(), pd.Timestamp(rep["latest"]).date()
    ref_first, ref_last = pd.Timestamp(ref["first"]).date(), pd.Timestamp(ref["latest"]).date()
    version_weeks = (rep_last - rep_first).days // 7
    return {
        "status": "ok",
        "event_history_weeks": (ref_last - ref_first).days // 7,
        "version_history_weeks": version_weeks,
        "event_weeks_without_version_history": (rep_first - ref_first).days // 7,
        # One national decision per week, so this is the largest denominator N1
        # could have before maturity and label availability prune it. Reported
        # as a ceiling, never as the achieved sample size.
        "max_weekly_national_cuts": version_weeks,
        "note": (
            "Data coverage is not version coverage. The eligible universe is "
            "bounded by the version history, not by how far the event series goes."
        ),
    }


def verdict(ceiling: dict, reconstruction: dict, metadata: dict) -> dict:
    reasons = []
    if metadata.get("status") != "ok":
        return {"verdict": "STOP_SOURCE", "reasons": ["source metadata unavailable"]}

    cuts = ceiling.get("max_weekly_national_cuts", 0)
    if cuts >= MIN_CUTS_PROCEED:
        level = "PROCEED"
    elif cuts >= MIN_CUTS_REDUCE:
        level = "REDUCE"
        reasons.append(f"only {cuts} weekly cuts available; narrow the inference universe")
    else:
        level = "STOP_SOURCE"
        reasons.append(f"{cuts} weekly cuts cannot support the central experiment")

    if reconstruction.get("status") == "ok" and not reconstruction.get("all_cuts_reconstruct"):
        reasons.append(
            "archive does not reconstruct snapshot exactly at every cut; "
            "restrict as-of reconstruction to /snapshot/ and declare the query cost"
        )
    if not all(metadata["signals_present"].values()):
        reasons.append("a declared signal is missing by name")

    return {
        "verdict": level,
        "thresholds": {"proceed_at": MIN_CUTS_PROCEED, "reduce_at": MIN_CUTS_REDUCE},
        "reasons": reasons or ["all declared criteria met"],
    }


def main() -> int:
    budget = Budget()
    started = datetime.now(UTC).isoformat()

    metadata = probe("G0.1-2 metadata", probe_metadata, budget)
    calendar = probe("G0.4 publication calendar", probe_calendar, budget)
    semantics = probe(
        "G0.3 archive semantics", lambda: probe_archive_semantics(calendar), budget
    )
    reconstruction = probe(
        "G0.3 archive vs snapshot", probe_reconstruction, budget, cost=2 * len(RECONSTRUCTION_CUTS)
    )
    coverage = probe("G0.4 coverage signals", probe_coverage_signals, budget, cost=2)
    hub = probe("G0.5 hub alignment", probe_hub_alignment, budget, cost=2)

    ceiling = support_ceiling(metadata)
    dictamen = verdict(ceiling, reconstruction, metadata)

    payload = {
        "run": {
            "started_at": started,
            "spec": "When_the_Past_Moves_Especificacion_Ejecutable_V3_3_2026.txt",
            "budget": budget.report(),
        },
        "g0_1_2_metadata": metadata,
        "g0_3_archive_semantics": semantics,
        "g0_3_reconstruction": reconstruction,
        "g0_4_calendar": calendar,
        "g0_4_coverage_signals": coverage,
        "g0_5_hub_alignment": hub,
        "g0_6_support": ceiling,
        "verdict": dictamen,
    }

    path = sources.write_json(
        sources.ROOT / "reports" / "results" / "00_source_feasibility.json", payload
    )

    print()
    print("=" * 72)
    if metadata.get("status") == "ok":
        print(f"reference_time : {metadata['reference_time_range']}")
        print(f"report_time    : {metadata['report_time_range']}")
    if ceiling.get("status") == "ok":
        print(f"version history: {ceiling['version_history_weeks']} weeks")
        print(f"ceiling for N1 : {ceiling['max_weekly_national_cuts']} weekly national cuts")
    if semantics.get("status") == "ok":
        print(f"archive        : {semantics['semantics_verdict']}")
    if calendar.get("status") == "ok":
        print(
            f"calendar       : {calendar['publication_dates']} publications, "
            f"weekly-cadence assumption holds: {calendar['weekly_cadence_assumption_holds']}"
        )
    print(f"VERDICT        : {dictamen['verdict']}")
    for reason in dictamen["reasons"]:
        print(f"  - {reason}")
    print(f"budget         : {budget.report()}")
    print("=" * 72)
    print(f"wrote {path.relative_to(sources.ROOT)}")
    print("Add a Claim row to scripts/verify_results.py in the same commit that")
    print("puts any of these numbers in a document.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
