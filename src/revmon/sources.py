"""The only module allowed to talk to the network.

Two channels, deliberately not merged:

1. **Delphi Epidata V5, `source="nhsn"`** — the candidate canonical source. Its
   `/archive/` and `/snapshot/` endpoints carry the revision history, and
   `epidata_meta` reports each source's `reference_time_range` and
   `report_time_range`. Access goes through `epidatpy`, Delphi's own client,
   rather than a hand-rolled HTTP layer: the V3/V4 methods are being deprecated
   as of October 2026, and reimplementing the wire protocol would put auth,
   pagination and parameter names on us for no gain.

2. **The FluSight hub's git history** — a second, independent reconstruction of
   what was published when. A commit is evidence of what the hub put in its own
   repository at a moment; it is **not** the instant a value became available
   from NHSN, and it is not an independent epidemiological measurement. The two
   channels are compared, never fused.

**What `/archive/` returns, measured in G0 rather than read.** The V5 overview
page calls its rows diffs — *"Each row represents a 'diff'"* — while the client's
docstring says *"Every version of each value is returned, one row per
report_time"*. **Neither is what happens.** Over a window with both axes bounded,
100 of 102 publications carried a row for the target signal, and a given event
week appeared in 17 of them at the median (min 2, max 41). Unchanged
republications are kept, and keys are absent from most publications: each release
restates a trailing window of weeks. So the revision-rate denominator is
publication pairs in which the key appeared on both sides — never "rows this
endpoint returned". Reconstructing a snapshot from the archive reproduced the
direct `/snapshot/` exactly at all three test cuts.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, date, datetime
from io import StringIO
from pathlib import Path
from typing import Any

import requests
from epidatpy import EpiDataContext

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
CACHE = ROOT / "data" / "cache"

# ---------------------------------------------------------------------------
# Channel 1: Delphi Epidata V5
# ---------------------------------------------------------------------------

V5_SOURCE = "nhsn"

#: Weekly laboratory-confirmed influenza hospital admissions (CDC field
#: `totalconfflunewadm`). The prediction target.
TARGET_SIGNAL = "confirmed_admissions_flu_ew"

#: Number of acute care hospitals reporting influenza admissions (CDC field
#: `totalconfflunewadmhosprep`). A **facility count**, not an admissions count:
#: the `hosprep_` prefix marks reporting coverage, and confusing the two would
#: turn a coverage change into an apparent epidemiological one.
COVERAGE_COUNT_SIGNAL = "hosprep_confirmed_admissions_flu_ew"

#: Percentage of active facilities submitting the metric. **Confirmed by name in
#: G0** against the source's 319 signals — it was carried as unconfirmed until
#: then, because the `hosprep_pct_*` family being documented does not guarantee
#: this member.
COVERAGE_PCT_SIGNAL = "hosprep_pct_confirmed_admissions_flu_ew"

GEO_TYPE = "nation"

# Reporting-regime boundaries, verified against CDC/CMS publications. A regime
# change alters coverage without altering the phenomenon, which is the worst
# available confounder for this project, so the eligible universe is declared
# from these dates rather than chosen after looking at results.
MANDATE_ENDED = date(2024, 4, 30)
VOLUNTARY_FROM = date(2024, 5, 1)
VOLUNTARY_UNTIL = date(2024, 10, 31)
MANDATE_RESUMED = date(2024, 11, 1)

API_KEY_ENV = "DELPHI_EPIDATA_KEY"

#: Anonymous access is capped at 60 requests/hour and allows multiple selections
#: on at most two parameters; a free key lifts both. `snapshot` filters
#: `geo_values` and `reference_time` client-side, so each snapshot call pays for
#: the whole dataset — which is why the reconstruction needs a query budget and
#: not a loop.
ANONYMOUS_REQUESTS_PER_HOUR = 60


def api_key_present() -> bool:
    """Whether a key is configured. Never returns or logs the key itself."""
    return bool(os.environ.get(API_KEY_ENV, "").strip())


def context(*, use_cache: bool = True, cache_max_age_days: int = 7) -> EpiDataContext:
    """A V5 client with on-disk caching delegated to `epidatpy`.

    The key is read from the environment by the client; it is never passed as an
    argument here, so it cannot end up in a traceback or a provenance record.
    """
    return EpiDataContext(use_cache=use_cache, cache_max_age_days=cache_max_age_days)


@dataclass(frozen=True)
class Provenance:
    """What a reconstruction needs in order to be auditable.

    `request_url` is the reproducible query; `observed_at` is when *we* fetched
    it, which is a fact about this system and not about the source.
    """

    request_url: str
    observed_at: str
    channel: str

    def as_dict(self) -> dict[str, str]:
        return {
            "request_url": self.request_url,
            "observed_at": self.observed_at,
            "channel": self.channel,
        }


def _now() -> str:
    return datetime.now(UTC).isoformat()


#: The CAST API base, which is where V5's metadata endpoints live. `epidatpy`
#: wraps snapshot, archive, meta and aux, but **not** the publication calendar,
#: so that one is reached directly from here — still inside the single door.
CAST_BASE = "https://delphi.cmu.edu/epidata/v5/"


def date_range(start: str | date, end: str | date) -> Any:
    """An inclusive range for `reference_time`/`report_time` filters.

    Exists so that callers never have to import the client themselves: the
    single-door rule is about who may import a network client, not only about
    who opens a socket.
    """
    from epidatpy import EpiRange

    return EpiRange(start, end)


def v5_report_times(source: str = V5_SOURCE) -> tuple[list[str], Provenance]:
    """The source's publication calendar: every date it released data.

    This is the denominator's only honest basis. The revision rate cannot be
    computed over "rows `/archive/` returned", because if that endpoint omits
    unchanged republications then dividing by its rows inflates the rate.

    The key travels as HTTP basic auth rather than a query parameter, so the
    `request_url` kept as provenance cannot carry the secret.
    """
    key = os.environ.get(API_KEY_ENV, "").strip()
    response = requests.get(
        f"{CAST_BASE}metadata/report_times/",
        params={"source": source},
        auth=("epidata", key) if key else None,
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    payload = response.json()
    return payload["report_times"], Provenance(
        response.url, _now(), "delphi_v5_report_times"
    )


def v5_metadata(source: str | None = V5_SOURCE, *, ctx: EpiDataContext | None = None) -> Any:
    """Source-level metadata, including `reference_time_range` and
    `report_time_range`.

    This is the single call that answers how far back the version history
    actually reaches — the question the documentation does not answer and that
    the data coverage start of 2020-08-08 must not be mistaken for.
    """
    return (ctx or context()).epidata_meta(source)


def v5_snapshot(
    *,
    signals: str | list[str],
    geo_type: str = GEO_TYPE,
    snapshot_date: str | date | None = None,
    reference_time: Any = "*",
    geo_values: Any = "*",
    ctx: EpiDataContext | None = None,
) -> tuple[Any, Provenance]:
    """The dataset as it stood at one release, plus its provenance."""
    call = (ctx or context()).epidata_snapshot(
        source=V5_SOURCE,
        signals=signals,
        geo_type=geo_type,
        geo_values=geo_values,
        reference_time=reference_time,
        snapshot_date=snapshot_date,
    )
    return call.df(), Provenance(call.request_url(), _now(), "delphi_v5_snapshot")


def v5_archive(
    *,
    signals: str | list[str],
    geo_type: str = GEO_TYPE,
    report_time: Any = "*",
    reference_time: Any = "*",
    geo_values: Any = "*",
    ctx: EpiDataContext | None = None,
) -> tuple[Any, Provenance]:
    """Version history, plus its provenance.

    `report_time` is filtered server-side; `geo_values` and `reference_time` are
    filtered by the client after the response arrives. What the rows *mean* —
    every version, or only the changes — is the open question in this module's
    docstring and is settled by G0, not here.
    """
    call = (ctx or context()).epidata_archive(
        source=V5_SOURCE,
        signals=signals,
        geo_type=geo_type,
        geo_values=geo_values,
        reference_time=reference_time,
        report_time=report_time,
    )
    return call.df(), Provenance(call.request_url(), _now(), "delphi_v5_archive")


# ---------------------------------------------------------------------------
# Channel 2: the FluSight hub's git history
# ---------------------------------------------------------------------------

HUB_REPO = "cdcepi/FluSight-forecast-hub"
HUB_TARGET = "target-data/target-hospital-admissions.csv"
HUB_BRANCH = "main"

GITHUB_API = "https://api.github.com"
GITHUB_RAW = "https://raw.githubusercontent.com"

TIMEOUT = 60


@dataclass(frozen=True)
class HubVersion:
    """One commit that touched the hub's target file."""

    sha: str
    committed_at: str  # ISO 8601 UTC, from the commit
    message: str


def hub_versions(limit: int = 300) -> list[HubVersion]:
    """Every commit that touched the target file, newest first.

    The history only grows at the tail, so a published version never changes
    and caching it is safe. Unauthenticated GitHub API calls are rate limited.
    """
    versions: list[HubVersion] = []
    page = 1
    while len(versions) < limit:
        response = requests.get(
            f"{GITHUB_API}/repos/{HUB_REPO}/commits",
            params={"path": HUB_TARGET, "per_page": 100, "page": page},
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        batch = response.json()
        if not batch:
            break
        for commit in batch:
            versions.append(
                HubVersion(
                    sha=commit["sha"],
                    committed_at=commit["commit"]["committer"]["date"],
                    message=commit["commit"]["message"].splitlines()[0],
                )
            )
        page += 1
    return versions[:limit]


def hub_national_series(sha: str = HUB_BRANCH) -> tuple[Any, Provenance]:
    """The hub's national weekly target values, as a tidy frame.

    Parsing a channel's wire format belongs to the adapter that owns that
    channel, not to a script: a script that parsed this CSV itself would be a
    second route to the data, and the single-door hook reports it as one.

    Returns columns `week` and `hub_value`. Locations are matched case
    insensitively against the hub's national coding, and the frame is empty
    rather than guessed if none matches.
    """
    import pandas as pd

    text, provenance = hub_target_at(sha)
    frame = pd.read_csv(StringIO(text), dtype={"location": str})
    national = frame[frame["location"].str.upper().isin({"US", "NATION"})]
    tidy = (
        national.assign(week=pd.to_datetime(national["date"]).dt.date)[["week", "value"]]
        .rename(columns={"value": "hub_value"})
        .drop_duplicates("week")
        .sort_values("week")
        .reset_index(drop=True)
    )
    return tidy, provenance


def hub_target_at(sha: str = HUB_BRANCH, *, use_cache: bool = True) -> tuple[str, Provenance]:
    """The target file as it stood at one commit.

    `sha="main"` is the branch tip, which is not a fixed version and is
    therefore never cached under a version name.
    """
    url = f"{GITHUB_RAW}/{HUB_REPO}/{sha}/{HUB_TARGET}"
    if sha == HUB_BRANCH:
        response = requests.get(url, timeout=TIMEOUT)
        response.raise_for_status()
        return response.text, Provenance(url, _now(), "flusight_hub_tip")

    path = RAW / "hub_versions" / f"{sha[:12]}.csv"
    if use_cache and path.exists():
        return path.read_text(encoding="utf-8"), Provenance(url, _now(), "flusight_hub_cached")

    response = requests.get(url, timeout=TIMEOUT)
    response.raise_for_status()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(response.text, encoding="utf-8")
    return response.text, Provenance(url, _now(), "flusight_hub")


# ---------------------------------------------------------------------------
# Evidence writing. Moves to evidence.py when G1 gives it company.
# ---------------------------------------------------------------------------


def write_json(path: Path, payload: object) -> Path:
    """Every script writes its result here, and every claim points at one key.

    Sorted keys are not cosmetic: the diff of a results file is part of the
    evidence, and a reordered dump would hide a changed number in noise.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path
