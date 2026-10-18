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

import hashlib
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
G1 = "01_vertical_slice.json"
G1A = "01_modeling_support.json"

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
    # G1-A support. These are the figures that replace an earlier review's
    # unmeasured guess of "40-60 folds"; the real count is nearly double, which
    # is exactly why the guess was never allowed into a document.
    Claim(
        label="candidate scheduled cuts",
        source=G1A,
        path=("temporally_eligible_origins", "candidate_scheduled_cuts"),
        expected=100,
        tolerance=0,
    ),
    Claim(
        label="eligible origins, declared 45-day policy",
        source=G1A,
        path=("temporally_eligible_origins", "declared_policy_origins"),
        expected=93,
        tolerance=0,
    ),
    Claim(
        label="eligible origins, 90-day sensitivity",
        source=G1A,
        path=("temporally_eligible_origins", "by_maturity_days", "90", "origins"),
        expected=87,
        tolerance=0,
    ),
    Claim(
        label="publication lag, max days",
        source=G1A,
        path=("publication_lag_days", "max"),
        expected=49,
        tolerance=0,
    ),
    Claim(
        label="publication lag, median days",
        source=G1A,
        path=("publication_lag_days", "median"),
        expected=7,
        tolerance=0,
    ),
    # Zero by construction at horizon +1. If this ever stops being zero, the
    # word "nowcast" in the README is wrong and this row says so.
    Claim(
        label="pre-week forecasts on disk",
        source=G1,
        path=("emission_audit", "pre_week_forecasts"),
        expected=0,
        tolerance=0,
    ),
    Claim(
        label="predictions with unverifiable emission",
        source=G1,
        path=("emission_audit", "not_verifiable"),
        expected=0,
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
    # The claim the project now makes about what it emits. If a future run ever
    # produced a pre-week forecast this row would fail, which is the point: the
    # word "nowcast" in the README would then be wrong.
    ExactClaim(
        label="observed run emission class",
        source=G1,
        path=("observed_run", "emission_class"),
        expected="intra_week_nowcast",
    ),
]

# --- claims about the manifest, checked per schema version ------------------
#
# Separate from the rows above because the question is different: not "does the
# published figure still match the artefact", but "does this run name the
# documents that governed it". And it is version-aware on purpose. A run written
# last week must not be required to match a document edited after it, or every
# past result would turn red the moment a typo is fixed. Older schemas are
# verified under the contract they were written with, and the absence of a newer
# field is never a failure.

SEALED_DOCUMENTS = {
    "spec_sha256": "When_the_Past_Moves_Especificacion_Ejecutable_V3_3_2026.txt",
    "g1_mp_plan_sha256": "When_the_Past_Moves_Plan_Ejecucion_Realista_G1_MP_V3_3_2026.txt",
}

#: Which sealed documents each manifest schema is required to carry.
SCHEMA_REQUIREMENTS: dict[int, tuple[str, ...]] = {
    1: ("spec_sha256",),
    2: ("spec_sha256", "g1_mp_plan_sha256"),
}

MANIFEST_SOURCES = (G1, G1A)


def sha256_file(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def check_manifests(root: Path | None = None) -> list[tuple[str, str]]:
    """Each manifest names its governing documents, and the hashes still match.

    A matching hash proves **identity of content, not date of predeclaration**.
    It says the plan has not been edited since the run; it says nothing about
    whether the plan existed before the selection cohort was scored. That needs
    the two external bounds in `.claude/rules/metodo.md`, and it is P4's job.

    `root` exists so the rejection can be tested on a **copy**: proving that a
    changed document fails must not require editing the sealed one.
    """
    base = root or ROOT
    results = base / "reports" / "results"
    failures: list[tuple[str, str]] = []
    live = {field: sha256_file(base / name) for field, name in SEALED_DOCUMENTS.items()}

    print(f"\n{'manifest seal':42}{'schema':>10}{'document':>30}{'state':>12}")
    for source in MANIFEST_SOURCES:
        path = results / source
        if not path.exists():
            print(f"{source:42}{'-':>10}{'-':>30}{'ABSENT':>12}")
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        manifest = payload.get("manifest", {})
        schema = int(manifest.get("schema_version", 1))
        required = SCHEMA_REQUIREMENTS.get(schema)
        if required is None:
            failures.append((source, f"unknown manifest schema_version {schema}"))
            print(f"{source:42}{schema:>10}{'-':>30}{'UNKNOWN':>12}")
            continue

        for field in required:
            stored = manifest.get(field)
            document = SEALED_DOCUMENTS[field]
            label = f"{source} :: {field}"
            if stored is None:
                failures.append((label, f"schema {schema} requires {field}, absent"))
                state = "MISSING"
            elif live[field] is None:
                failures.append((label, f"{document} is not on disk"))
                state = "NO FILE"
            elif stored != live[field]:
                failures.append((
                    label,
                    f"{document} changed since the run (stored {stored[:12]}..., "
                    f"on disk {live[field][:12]}...)",
                ))
                state = "CHANGED"
            else:
                state = "ok"
            print(f"{label:42}{schema:>10}{document[-29:]:>30}{state:>12}")

        # Fields the schema does not require are reported, never demanded.
        for field in SEALED_DOCUMENTS:
            if field not in required and manifest.get(field) is not None:
                print(f"{source + ' :: ' + field:42}{schema:>10}"
                      f"{'(beyond schema)':>30}{'noted':>12}")
    return failures


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

    seal_failures = check_manifests()
    failures.extend(seal_failures)
    print(f"\nmanifest seals: {'ok' if not seal_failures else 'FAILED'}")

    if failures:
        print("\nfailed:")
        for label, detail in failures:
            print(f"  {label}: {detail}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
