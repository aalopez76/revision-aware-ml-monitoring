"""The canonical panel, and the as-of gate. The only door to the data.

One row per source x signal x geography x event week x published version. That
shape is a revision triangle: reading down a key shows how one week's value was
successively restated, and taking the latest version at or before a cut shows
what the world looked like at that moment.

No other module may read `data/`. The reason is not tidiness: the project's
central quantity is *what was knowable when*, so a second route to the data is a
second definition of that quantity, and that is how a look-ahead gets in without
anyone seeing it.

Two things live here and are deliberately separate:

* `derive_revisions` turns stacked versions into the triangle. Pure, so the
  revision logic is testable on synthetic frames with no network.
* `as_of_view` is the gate: given a cut and a replay mode, it returns what was
  visible and nothing else. Pure as well, and the invariant it enforces is the
  one the whole project rests on, which is why it is property-tested rather than
  checked with a handful of examples.

`load_as_of` is the public contract that composes a source read with the gate.
Its loading half waits for G0 to measure the source contract; writing it against
an assumed contract is what the specification forbids.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from revmon import sources
from revmon.temporal import (
    Completeness,
    MaturityPolicy,
    ReplayMode,
    latest_usable_report_date,
)

DERIVED = sources.ROOT / "data" / "derived"
PANEL = DERIVED / "panel.parquet"

#: What identifies one observation. Everything downstream groups by this.
#:
#: `fill_method` is here because the source puts it in its own `key_columns`,
#: measured in G0: `signal · report_time · geo_type · geo_value · fill_method ·
#: reference_time`. Two rows differing only in that field are not a revision of
#: one another, and leaving it out would count a method change as a restatement.
KEY = ["source", "signal", "geo_type", "geo_value", "fill_method", "event_week_end"]

#: The two clocks that can order publications. `derive_revisions` refuses to
#: pick for you: a hub commit is not a Delphi report date, and ordering the
#: triangle by the wrong one silently redefines what "the next version" means.
PUBLICATION_CLOCKS = ("source_report_date", "hub_commit_at")

PANEL_COLUMNS = [
    # identity
    "source",
    "signal",
    "geo_type",
    "geo_value",
    "fill_method",
    # the clocks
    "event_week_end",
    "source_report_date",
    "hub_commit_at",
    "observed_at",
    "vintage_id",
    # the value and what the triangle derives from it
    "value",
    "lag_days",
    "release_index",
    "is_first_release",
    "revision",
    "revised",
]


class PanelContractError(ValueError):
    """The frame does not satisfy what the panel promises."""


def derive_revisions(frame: pd.DataFrame, *, publication_clock: str) -> pd.DataFrame:
    """Turn stacked published versions into the revision triangle.

    `publication_clock` names which clock orders the versions and must be one of
    `PUBLICATION_CLOCKS`. There is no default: the project's own rule is that a
    git commit is not equated with a source publication date without proof, and
    a function that guessed would quietly break that rule.

    A version whose values are identical to the previous one is **kept**: a
    republication that changed nothing is evidence that nothing was revised, and
    dropping it would bias the revision rate downwards.
    """
    if publication_clock not in PUBLICATION_CLOCKS:
        raise PanelContractError(
            f"publication_clock must be one of {PUBLICATION_CLOCKS}, got {publication_clock!r}"
        )
    missing = [c for c in [*KEY, publication_clock, "value", "vintage_id"] if c not in frame]
    if missing:
        raise PanelContractError(f"frame is missing required columns: {missing}")
    if frame[publication_clock].isna().any():
        raise PanelContractError(
            f"{publication_clock} has missing values; a version without a publication "
            "date cannot be placed in the triangle, and imputing one would invent "
            "the very quantity this project measures"
        )

    panel = frame.copy()
    for column in PANEL_COLUMNS:
        if column not in panel:
            panel[column] = pd.NA

    clock = pd.to_datetime(panel[publication_clock])
    event = pd.to_datetime(panel["event_week_end"])
    if getattr(clock.dtype, "tz", None) is not None:
        clock = clock.dt.tz_localize(None)
    panel["lag_days"] = (clock - event).dt.days

    panel = panel.sort_values([*KEY, publication_clock]).reset_index(drop=True)
    group = panel.groupby(KEY, sort=False, dropna=False)
    panel["release_index"] = group.cumcount()
    panel["is_first_release"] = panel["release_index"] == 0
    panel["revision"] = group["value"].diff()
    panel["revised"] = panel["revision"].fillna(0) != 0
    return panel[PANEL_COLUMNS]


def visible_triangle(
    panel: pd.DataFrame,
    decision_as_of: date,
    mode: ReplayMode,
) -> pd.DataFrame:
    """Every version visible at the cut, **without collapsing to one per key**.

    This is the half of the gate a monitor needs and a forecaster does not. A
    forecast consumes one value per week, so `as_of_view` collapses; a revision
    signal is about the versions themselves, so collapsing would delete the
    quantity being measured.

    It exists here, and not as a filter inside a script, because the visibility
    rule is the project's central definition: two implementations of it are two
    definitions of what was knowable when. `as_of_view` is built on top of this
    function for that reason, so there is exactly one.
    """
    if panel.empty:
        return panel.copy()
    if mode is ReplayMode.LIVE:
        return panel

    # Compared as timestamps rather than Python dates: a column that is all
    # NaT keeps its datetime dtype, and comparing that against a `date`
    # raises instead of filtering. A gate that can raise on empty input is a
    # gate that fails open in exactly the case it exists for.
    cutoff = pd.Timestamp(latest_usable_report_date(decision_as_of, mode))
    report = pd.to_datetime(panel["source_report_date"], errors="coerce")
    visible = panel[report.notna() & (report <= cutoff)]

    if mode is ReplayMode.OBSERVED_REPLAY:
        # A row we never observed cannot be part of a replay of what we saw.
        # The bound is the end of the cut day, so "observed on the cut date"
        # counts and nothing later does.
        observed = pd.to_datetime(visible["observed_at"], utc=True, errors="coerce")
        limit = pd.Timestamp(decision_as_of, tz="UTC") + pd.Timedelta(days=1)
        visible = visible[observed.notna() & (observed < limit)]

    return visible


def as_of_view(
    panel: pd.DataFrame,
    decision_as_of: date,
    mode: ReplayMode,
) -> tuple[pd.DataFrame, Completeness]:
    """What was visible at `decision_as_of`, and nothing published after it.

    Returns one row per key: the newest version at or before the cut. That is
    the state a forecast or a monitor is allowed to consume.

    * `PUBLIC_REPLAY` keeps versions the source declared published before the
      cut, with the day-granularity margin applied, because a publication date
      without an hour does not demonstrate same-day visibility.
    * `OBSERVED_REPLAY` additionally requires that this system had actually
      fetched the version by the cut.
    * `LIVE` takes the frame as given: it was fetched and sealed in this run.

    This is the function that makes the central invariant real. It is enforced
    here, in the data path, rather than by a guard that pattern-matches script
    names — which is the wrong layer and blocks developing the evaluation code
    it is supposed to protect.
    """
    if panel.empty:
        return panel.copy(), Completeness.INCOMPLETE_HISTORY

    visible = visible_triangle(panel, decision_as_of, mode)

    if visible.empty:
        return visible.copy(), Completeness.INCOMPLETE_HISTORY

    latest = visible.sort_values([*KEY, "release_index"]).groupby(KEY, as_index=False, dropna=False)
    return latest.last().reset_index(drop=True), Completeness.COMPLETE


def eligible_labels(
    panel: pd.DataFrame,
    decision_as_of: date,
    policy: MaturityPolicy,
    mode: ReplayMode = ReplayMode.PUBLIC_REPLAY,
) -> pd.DataFrame:
    """Rows whose label may be scored at the cut, under a declared policy.

    Two conditions, both required: the period is old enough under `policy`, and
    the version carrying its value was visible at the cut. Scoring a label that
    matured only later is the second way a look-ahead enters, after features.
    """
    visible, status = as_of_view(panel, decision_as_of, mode)
    if status is not Completeness.COMPLETE:
        return visible.iloc[0:0]
    weeks = pd.to_datetime(visible["event_week_end"]).dt.date
    return visible[[policy.is_eligible(w, decision_as_of) for w in weeks]]


def panel_summary(panel: pd.DataFrame) -> dict:
    """Scale figures. Every count a document quotes comes from here.

    Explicit conversions throughout: a results file that is part of the evidence
    should not carry numpy types that serialise differently between versions.
    """
    later = panel[~panel["is_first_release"].astype(bool)]
    return {
        "rows": int(len(panel)),
        "sources": sorted(panel["source"].dropna().unique().tolist()),
        "signals": sorted(panel["signal"].dropna().unique().tolist()),
        "geographies": int(panel["geo_value"].nunique()),
        "event_weeks": int(panel["event_week_end"].nunique()),
        "versions": int(panel["vintage_id"].nunique()),
        "first_releases": int(panel["is_first_release"].astype(bool).sum()),
        "later_releases": int(len(later)),
        "revised_rows": int(panel["revised"].astype(bool).sum()),
        "revised_fraction_of_later": (
            float(later["revised"].astype(bool).mean()) if len(later) else None
        ),
        "earliest_event_week": str(pd.to_datetime(panel["event_week_end"]).min().date()),
        "latest_event_week": str(pd.to_datetime(panel["event_week_end"]).max().date()),
    }


def load_panel() -> pd.DataFrame:
    """The panel as built. Fails loudly rather than rebuilding silently.

    An implicit rebuild inside an analysis would change the data under the
    analysis's feet, which is indistinguishable from a bug you cannot see.
    """
    if not PANEL.exists():
        raise FileNotFoundError(
            f"{PANEL} is missing. It is built by the G0/G1 entry points, which are "
            "the only things that write it."
        )
    return pd.read_parquet(PANEL)


FROZEN_ACT = sources.ROOT / "reports" / "results" / "frozen_method.json"


def panel_from_v5(frame: pd.DataFrame, observed_at: str) -> pd.DataFrame:
    """Map a V5 archive response onto the canonical panel, then derive.

    The column mapping is the whole point and it is one-way on purpose:
    `report_time` becomes `source_report_date` — the publication the source
    declares — and never `hub_commit_at`, which belongs to the other channel.
    `vintage_id` carries the publication's identity, not its date.

    `observed_at` is supplied rather than stamped here so that a rebuild of the
    same response is reproducible: a function that reached for the clock itself
    could not be replayed.
    """
    mapped = pd.DataFrame(
        {
            "source": sources.V5_SOURCE,
            "signal": frame["signal"],
            "geo_type": frame["geo_type"],
            "geo_value": frame["geo_value"],
            "fill_method": frame["fill_method"],
            "event_week_end": pd.to_datetime(frame["reference_time"]),
            "source_report_date": pd.to_datetime(frame["report_time"]).dt.tz_localize(None),
            "hub_commit_at": pd.NaT,
            "observed_at": observed_at,
            "vintage_id": frame["report_time"].astype(str),
            "value": frame["value"],
        }
    )
    return derive_revisions(mapped, publication_clock="source_report_date")


def load_as_of(
    decision_as_of: date,
    *,
    signal: str = sources.TARGET_SIGNAL,
    geography: str = sources.GEO_TYPE,
    replay_mode: ReplayMode = ReplayMode.PUBLIC_REPLAY,
    confirmatory: bool = False,
) -> tuple[pd.DataFrame, Completeness]:
    """The public contract: the state of the data valid for one decision cut.

    Composed from one `/archive/` pull rather than a `/snapshot/` per cut, which
    G0 licensed by measuring that the reconstruction reproduces the direct
    snapshot exactly at three test cuts. That matters for cost: `/snapshot/`
    filters geography and reference time client-side, so each call pays for the
    whole dataset.

    `report_time` is bounded server-side at the cut, so a version published after
    it never enters the process at all — the gate in `as_of_view` is then the
    second line and not the only one.

    `confirmatory=True` is refused unless the frozen act exists. This is what
    replaces the retired filename guard, and it sits in the data path where the
    control belongs: a caller cannot reach the confirmatory cohort by renaming a
    script.
    """
    triangle, _ = fetch_triangle_as_of(
        decision_as_of, signal=signal, geography=geography, confirmatory=confirmatory
    )
    if triangle.empty:
        return triangle, Completeness.DATA_UNAVAILABLE
    return as_of_view(triangle, decision_as_of, replay_mode)


def fetch_triangle_as_of(
    decision_as_of: date,
    *,
    signal: str = sources.TARGET_SIGNAL,
    geography: str = sources.GEO_TYPE,
    confirmatory: bool = False,
) -> tuple[pd.DataFrame, sources.Provenance | None]:
    """The whole revision triangle that was visible at a cut.

    `load_as_of` collapses this to one row per key, which is what a forecast
    consumes. A monitor needs the triangle itself — it is what makes a
    restatement observable at all — so both are exposed rather than having a
    caller rebuild one from the other and get the clock wrong.
    """
    if confirmatory and not FROZEN_ACT.exists():
        raise PanelContractError(
            f"a confirmatory cut needs a frozen method: {FROZEN_ACT.name} does not "
            "exist. Freeze first, deliberately, with /congelar-metodo. The cohort's "
            "entire value comes from the method being fixed before it was scored."
        )

    frame, provenance = sources.v5_archive(
        signals=signal,
        geo_type=geography,
        report_time=sources.date_range("2024-11-01", decision_as_of),
    )
    if frame.empty:
        return frame, provenance
    return panel_from_v5(frame, observed_at=provenance.observed_at), provenance
