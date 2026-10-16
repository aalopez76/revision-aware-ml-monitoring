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


# ---------------------------------------------------------------------------
# The README currently states no figures: it is the framing, written before the
# analysis exists, and every number in it is deliberately absent rather than
# estimated. This list therefore starts empty, and grows one row per figure as
# each phase lands — in the same commit that puts the figure in the document.
#
# G0 will add the measured source windows from 00_source_feasibility.json; G1
# the first real run; G2 the discordance N1 with its numerator, denominator and
# abstentions; G3, only if the gate opens, the cost frontier. Until then an
# empty run passing is the correct and honest outcome, not a gap.
#
# This script checks correspondence between a published number and the artefact
# behind it. It does **not** check that the computation is right, and it cannot
# tell an E1 measurement from an E3 proposal — that needs judgement, which is
# why it lives in /auditar-cifras and not here.
# ---------------------------------------------------------------------------

CLAIMS: list[Claim] = []


def main() -> int:
    if not CLAIMS:
        print("0 tracked numerical claims: the README states no figures yet.")
        print("Add a Claim here in the same commit that puts a figure in the document.")
        return 0

    failures: list[tuple[str, str]] = []
    print(f"{'claim':42}{'README':>11}{'artefact':>11}")
    for claim in CLAIMS:
        try:
            actual = claim.read()
        except (KeyError, FileNotFoundError) as exc:
            failures.append((claim.label, f"not found: {exc}"))
            print(f"{claim.label:42}{claim.expected:11.4g}{'MISSING':>11}   FAIL")
            continue
        ok = abs(actual - claim.expected) <= claim.tolerance
        if not ok:
            failures.append((claim.label, f"{actual:.6g} against {claim.expected:.6g}"))
        print(f"{claim.label:42}{claim.expected:11.4g}{actual:11.4g}"
              f"   {'ok' if ok else 'FAIL'}")

    total = len(CLAIMS)
    print(f"\n{total - len(failures)}/{total} tracked numerical claims verified")
    if failures:
        print("\nfailed:")
        for label, detail in failures:
            print(f"  {label}: {detail}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
