"""Capture what the sources published this week, and leave a dated record.

This runs from the start, in parallel with everything else, and it is the only
piece of the project that cannot be recovered later: a publication can be
re-queried if the source keeps its history, but **the evidence that a run
happened on a given date cannot be reconstructed afterwards**. A replay is not a
run, and this script never relabels one as the other.

If a run did not happen, there is no file. That is the whole operational claim,
and it now holds in the other direction too: **if a run did happen, its record
stays.** One file per execution, never per week, because a second run in a week
used to overwrite the first.

Scope today: the FluSight hub channel, which is verified and working. The Delphi
V5 channel is added once G0.1 confirms authentication against a v5 path with a
real query — the specification is explicit that capture must not wait for the
analyses, and equally explicit that the V5 adapter must not be written against
an assumed contract.
"""

from __future__ import annotations

import argparse
import os
import uuid
from datetime import UTC, datetime

from revmon import evidence, sources

#: One record per **execution**, not per ISO week. The week stays in the name so
#: reconciliation can still group by it, and the execution identity follows.
#:
#: The earlier `AAAA-Wnn.json` keyed the record by week, so a second run in the
#: same week overwrote the first. Nothing was lost — the file is versioned and
#: the bot commits every run — but the *working tree* then showed one execution
#: where two had happened, and `/registro-semanal` reconciles against the files.
#: An execution that did happen must leave a record that stays.
#:
#: In Actions, `GITHUB_RUN_ID` and `GITHUB_RUN_ATTEMPT` are default variables, so
#: the pair identifies the execution exactly and a re-entered step is idempotent.
#: Locally there is no such identity, so one is minted per invocation: every local
#: run is a distinct execution and gets its own record.
RECORD_PATTERN = "{year}-W{week:02d}__{run}__a{attempt}.json"


def execution_id() -> tuple[str, str, bool]:
    """`(run, attempt, on_a_runner)` — the identity this record is filed under."""
    run_id = os.environ.get("GITHUB_RUN_ID", "").strip()
    if run_id:
        return run_id, os.environ.get("GITHUB_RUN_ATTEMPT", "1").strip() or "1", True
    # Not a GitHub variable and not derived from one: a local run is identified
    # by when it started plus enough entropy that two in the same second are
    # still two records rather than one silently overwriting the other.
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"local-{stamp}-{uuid.uuid4().hex[:6]}", "1", False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--limit", type=int, default=300, help="how many hub versions back to list"
    )
    parser.add_argument(
        "--no-record",
        action="store_true",
        help="query and report without writing the dated record (for a dry run)",
    )
    args = parser.parse_args()

    now = datetime.now(UTC)
    versions = sources.hub_versions(limit=args.limit)
    print(f"{len(versions)} published versions of {sources.HUB_TARGET}")

    cached = 0
    for version in versions:
        sources.hub_target_at(version.sha)
        cached += 1
    print(f"cached {cached} versions under data/raw/hub_versions/")

    tip, provenance = sources.hub_target_at()
    rows = tip.count("\n")
    print(f"branch tip carries {rows} rows")

    # Reported, never assumed: whether a key is configured decides whether the
    # V5 channel can be added at all, and it is the first thing G0.1 needs.
    print(f"V5 api key configured: {sources.api_key_present()}")

    if args.no_record:
        print("--no-record: nothing written")
        return 0

    run, attempt, on_a_runner = execution_id()
    record = {
        "run_at": now.isoformat(),
        "iso_year": now.isocalendar().year,
        "iso_week": now.isocalendar().week,
        # Added, not replacing: the previous schema's fields all keep their
        # names and meanings, so an older record stays readable as it is.
        "run_attempt": attempt,
        "scheduled_runner": on_a_runner,
        "channel": "flusight_hub",
        "hub_versions_known": len(versions),
        "newest_hub_version": {
            "sha": versions[0].sha,
            "committed_at": versions[0].committed_at,
            "message": versions[0].message,
        },
        "tip_rows": rows,
        "provenance": provenance.as_dict(),
        # `v5_api_key_configured` reports that the variable is PRESENT. It is not
        # evidence of a successful authentication: this capture reads the hub
        # channel and makes no V5 request at all.
        "v5_api_key_configured": sources.api_key_present(),
        "runner": run if on_a_runner else "local",
    }
    name = RECORD_PATTERN.format(
        year=now.isocalendar().year,
        week=now.isocalendar().week,
        run=run,
        attempt=attempt,
    )
    path = sources.ROOT / "reports" / "weekly" / name
    stored, wrote = evidence.write_json_once(path, record)
    if wrote:
        print(f"wrote {path.relative_to(sources.ROOT)}")
    else:
        # Same execution writing twice. The first record stands; it is not
        # restamped with a later time, and nothing is overwritten.
        print(
            f"{path.relative_to(sources.ROOT)} already exists for this execution; "
            f"kept the record written at {stored['run_at']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
