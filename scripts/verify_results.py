"""Check that the numerical claims in the README match the artefacts.

This asks a different question from the test suite. `pytest` asks whether the
software works; this asks whether the **published claims still correspond to the
files that back them**. Code can be correct while a document quietly drifts away
from it.

Each claim names where it appears, how to find it in `reports/results/`, and the
tolerance it is allowed. Tolerances are tight enough to catch a changed analysis
and loose enough to survive the last reported digit.

**This script and the README are updated in the same commit.** A number that
changes on purpose changes here too; one that changes by accident fails here
first. A figure that appears in the README without a row here is a defect, not
an exception.

It reads only versioned JSON, so it needs no data download and no recomputation,
which is why CI can run it.

Exit code is non-zero when any claim fails.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "reports" / "results"


@dataclass(frozen=True)
class Claim:
    """One number the README states, and where it comes from."""

    label: str
    source: str                      # file in reports/results/
    path: tuple[str | int, ...]      # keys to walk; ints index into lists
    expected: float
    tolerance: float
    scale: float = 1.0               # multiply the stored value before comparing

    def read(self) -> float:
        payload: Any = json.loads((RESULTS / self.source).read_text(encoding="utf-8"))
        for key in self.path:
            payload = payload[key]
        return float(payload) * self.scale


@dataclass(frozen=True)
class ExactClaim:
    """One non-numeric figure the README states: a date, a window, a verdict.

    Added because the rule is that **every** figure needs a row, and a date is a
    figure. A verifier that only tracked floats would have left the measured
    source windows — the most load-bearing numbers G0 produced — untraceable by
    construction, and that gap would read as compliance.
    """

    label: str
    source: str
    path: tuple[str | int, ...]
    expected: str

    def read(self) -> str:
        payload: Any = json.loads((RESULTS / self.source).read_text(encoding="utf-8"))
        for key in self.path:
            payload = payload[key]
        return str(payload)


# ---------------------------------------------------------------------------
# One row per figure the documents state, added in the same commit that puts the
# figure in the document. G0's measured source windows are here; G1 adds the
# first real run, G2 the discordance N1 with its numerator, denominator and
# abstentions, and G3 — only if the gate opens — the cost frontier.
#
# This script checks correspondence between a published number and the artefact
# behind it. It does **not** check that the computation is right, and it cannot
# tell an E1 measurement from an E3 proposal — that needs judgement, which is
# why it lives in /auditar-cifras and not here.
#
# Some of these grow: the publication calendar gains entries every few days, and
# the version history gains a week every week. That is not a flaw in the rows —
# it is the rule working. A figure that changes on purpose changes here and in
# the document together, which is why the documents date the run they quote.
# ---------------------------------------------------------------------------

G0 = "00_source_feasibility.json"

CLAIMS: list[Claim] = [
    Claim(
        label="event history, weeks",
        source=G0,
        path=("g0_6_support", "event_history_weeks"),
        expected=322,
        tolerance=0,
    ),
    Claim(
        label="version history, weeks",
        source=G0,
        path=("g0_6_support", "version_history_weeks"),
        expected=99,
        tolerance=0,
    ),
    Claim(
        label="event weeks with no version history",
        source=G0,
        path=("g0_6_support", "event_weeks_without_version_history"),
        expected=223,
        tolerance=0,
    ),
    Claim(
        label="ceiling: weekly national cuts",
        source=G0,
        path=("g0_6_support", "max_weekly_national_cuts"),
        expected=99,
        tolerance=0,
    ),
    Claim(
        label="publication dates in the calendar",
        source=G0,
        path=("g0_4_calendar", "publication_dates"),
        expected=189,
        tolerance=0,
    ),
    Claim(
        label="publications per ISO week, median",
        source=G0,
        path=("g0_4_calendar", "publications_per_iso_week", "median"),
        expected=2.0,
        tolerance=0,
    ),
    Claim(
        label="signals offered by the source",
        source=G0,
        path=("g0_1_2_metadata", "signals_total"),
        expected=319,
        tolerance=0,
    ),
    Claim(
        label="archive: publications in window",
        source=G0,
        path=("g0_3_archive_semantics", "calendar_publications_in_window"),
        expected=102,
        tolerance=0,
    ),
    Claim(
        label="archive: share of publications present",
        source=G0,
        path=("g0_3_archive_semantics", "share_of_publications_present"),
        expected=0.98,
        tolerance=0.005,
    ),
    Claim(
        label="archive: versions per key, median",
        source=G0,
        path=("g0_3_archive_semantics", "rows_per_key", "median"),
        expected=17.0,
        tolerance=0,
    ),
    Claim(
        label="archive: versions per key, min",
        source=G0,
        path=("g0_3_archive_semantics", "rows_per_key", "min"),
        expected=2,
        tolerance=0,
    ),
    Claim(
        label="hub cross-check: overlapping weeks",
        source=G0,
        path=("g0_5_hub_alignment", "overlapping_weeks"),
        expected=245,
        tolerance=0,
    ),
    Claim(
        label="hub cross-check: disagreeing weeks",
        source=G0,
        path=("g0_5_hub_alignment", "disagreeing_weeks"),
        expected=0,
        tolerance=0,
    ),
    Claim(
        label="G0 requests issued",
        source=G0,
        path=("run", "budget", "requests_issued"),
        expected=13,
        tolerance=0,
    ),
]

EXACT_CLAIMS: list[ExactClaim] = [
    ExactClaim(
        label="first recoverable report_time",
        source=G0,
        path=("g0_1_2_metadata", "report_time_range", "first"),
        expected="2024-11-19T00:00:00Z",
    ),
    ExactClaim(
        label="first reference_time",
        source=G0,
        path=("g0_1_2_metadata", "reference_time_range", "first"),
        expected="2020-08-08",
    ),
    ExactClaim(
        label="archive semantics verdict",
        source=G0,
        path=("g0_3_archive_semantics", "semantics_verdict"),
        expected="multiple_versions_per_key",
    ),
    ExactClaim(
        label="G0 verdict",
        source=G0,
        path=("verdict", "verdict"),
        expected="PROCEED",
    ),
]


def main() -> int:
    if not CLAIMS and not EXACT_CLAIMS:
        print("0 tracked claims: the documents state no figures yet.")
        print("Add a row here in the same commit that puts a figure in a document.")
        return 0

    failures: list[tuple[str, str]] = []
    print(f"{'claim':42}{'document':>26}{'artefact':>26}")
    for claim in CLAIMS:
        try:
            actual = claim.read()
        except (KeyError, FileNotFoundError) as exc:
            failures.append((claim.label, f"not found: {exc}"))
            print(f"{claim.label:42}{claim.expected:>26.6g}{'MISSING':>26}   FAIL")
            continue
        ok = abs(actual - claim.expected) <= claim.tolerance
        if not ok:
            failures.append((claim.label, f"{actual:.6g} against {claim.expected:.6g}"))
        print(f"{claim.label:42}{claim.expected:>26.6g}{actual:>26.6g}"
              f"   {'ok' if ok else 'FAIL'}")

    for exact in EXACT_CLAIMS:
        try:
            actual_text = exact.read()
        except (KeyError, FileNotFoundError) as exc:
            failures.append((exact.label, f"not found: {exc}"))
            print(f"{exact.label:42}{exact.expected:>26}{'MISSING':>26}   FAIL")
            continue
        ok = actual_text == exact.expected
        if not ok:
            failures.append((exact.label, f"{actual_text!r} against {exact.expected!r}"))
        print(f"{exact.label:42}{exact.expected:>26}{actual_text:>26}"
              f"   {'ok' if ok else 'FAIL'}")

    total = len(CLAIMS) + len(EXACT_CLAIMS)
    print(f"\n{total - len(failures)}/{total} tracked claims verified")
    if failures:
        print("\nfailed:")
        for label, detail in failures:
            print(f"  {label}: {detail}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
