"""Capture what the sources published this week, and leave a dated record.

This runs from the start, in parallel with everything else, and it is the only
piece of the project that cannot be recovered later: a publication can be
re-queried if the source keeps its history, but **the evidence that a run
happened on a given date cannot be reconstructed afterwards**. A replay is not a
run, and this script never relabels one as the other.

If a run did not happen, there is no file. That is the whole operational claim.

Scope today: the FluSight hub channel, which is verified and working. The Delphi
V5 channel is added once G0.1 confirms authentication against a v5 path with a
real query — the specification is explicit that capture must not wait for the
analyses, and equally explicit that the V5 adapter must not be written against
an assumed contract.
"""

from __future__ import annotations

import argparse
import os
from datetime import UTC, datetime

from revmon import sources


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

    record = {
        "run_at": now.isoformat(),
        "iso_year": now.isocalendar().year,
        "iso_week": now.isocalendar().week,
        "channel": "flusight_hub",
        "hub_versions_known": len(versions),
        "newest_hub_version": {
            "sha": versions[0].sha,
            "committed_at": versions[0].committed_at,
            "message": versions[0].message,
        },
        "tip_rows": rows,
        "provenance": provenance.as_dict(),
        "v5_api_key_configured": sources.api_key_present(),
        "runner": os.environ.get("GITHUB_RUN_ID", "local"),
    }
    name = f"{now.isocalendar().year}-W{now.isocalendar().week:02d}.json"
    path = sources.write_json(sources.ROOT / "reports" / "weekly" / name, record)
    print(f"wrote {path.relative_to(sources.ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
