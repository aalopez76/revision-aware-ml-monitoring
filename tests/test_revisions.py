"""Tests for the revision triangle and the as-of gate.

The triangle tests carry over from the previous schema, because the logic they
guard did not change: what changed is the names of the clocks. The as-of tests
are new and they are the ones that matter most — the no-look-ahead invariant is
universal, so it is checked with generated histories rather than three examples.
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from revmon.panel import (
    PANEL_COLUMNS,
    PanelContractError,
    as_of_view,
    derive_revisions,
    eligible_labels,
)
from revmon.temporal import AVAILABILITY_MARGIN_DAYS, Completeness, MaturityPolicy, ReplayMode

POLICY = MaturityPolicy(days=45, declared_in="tests")


def build(rows: list[dict], *, clock: str = "source_report_date") -> pd.DataFrame:
    """A panel from terse rows, with the identity columns defaulted."""
    frame = pd.DataFrame(rows)
    frame["source"] = frame.get("source", "nhsn")
    frame["signal"] = frame.get("signal", "confirmed_admissions_flu_ew")
    frame["geo_type"] = frame.get("geo_type", "nation")
    if "geo_value" not in frame:
        frame["geo_value"] = "us"
    if "vintage_id" not in frame:
        frame["vintage_id"] = frame[clock].astype(str)
    if "observed_at" not in frame:
        frame["observed_at"] = pd.to_datetime(frame[clock], utc=True)
    return derive_revisions(frame, publication_clock=clock)


# ---------------------------------------------------------------------------
# The triangle
# ---------------------------------------------------------------------------


def test_schema_is_the_declared_one():
    panel = build(
        [{"event_week_end": "2026-10-10", "source_report_date": "2026-10-14", "value": 1}]
    )
    assert list(panel.columns) == PANEL_COLUMNS


def test_first_release_is_marked_and_has_no_revision():
    panel = build(
        [{"event_week_end": "2026-10-10", "source_report_date": "2026-10-14", "value": 7}]
    )
    assert panel.loc[0, "is_first_release"]
    assert panel.loc[0, "release_index"] == 0
    assert pd.isna(panel.loc[0, "revision"])
    assert not panel.loc[0, "revised"]


def test_a_restated_value_is_a_revision_with_its_size():
    panel = build(
        [
            {"event_week_end": "2026-10-10", "source_report_date": "2026-10-14", "value": 100},
            {"event_week_end": "2026-10-10", "source_report_date": "2026-10-21", "value": 112},
        ]
    )
    assert panel.loc[1, "revision"] == 12
    assert panel.loc[1, "revised"]


def test_an_unchanged_republication_is_kept_but_not_a_revision():
    """The rule that keeps the revision rate from being biased downwards."""
    panel = build(
        [
            {"event_week_end": "2026-10-10", "source_report_date": "2026-10-14", "value": 100},
            {"event_week_end": "2026-10-10", "source_report_date": "2026-10-21", "value": 100},
        ]
    )
    assert len(panel) == 2
    assert not panel.loc[1, "revised"]
    assert panel.loc[1, "release_index"] == 1


def test_revisions_do_not_leak_across_geographies():
    panel = build(
        [
            {"event_week_end": "2026-10-10", "source_report_date": "2026-10-14",
             "value": 10, "geo_value": "us"},
            {"event_week_end": "2026-10-10", "source_report_date": "2026-10-14",
             "value": 99, "geo_value": "ca"},
        ]
    )
    assert panel["revised"].sum() == 0
    assert set(panel["release_index"]) == {0}


def test_revisions_do_not_leak_across_event_weeks():
    panel = build(
        [
            {"event_week_end": "2026-10-10", "source_report_date": "2026-10-14", "value": 10},
            {"event_week_end": "2026-10-17", "source_report_date": "2026-10-14", "value": 99},
        ]
    )
    assert panel["revised"].sum() == 0


def test_lag_days_is_computed_against_the_event_week():
    panel = build(
        [
            {"event_week_end": "2026-10-10", "source_report_date": "2026-10-14", "value": 1},
            {"event_week_end": "2026-10-10", "source_report_date": "2026-10-21", "value": 2},
        ]
    )
    assert list(panel["lag_days"]) == [4, 11]


def test_versions_are_ordered_by_publication_not_by_input_order():
    panel = build(
        [
            {"event_week_end": "2026-10-10", "source_report_date": "2026-10-21", "value": 112},
            {"event_week_end": "2026-10-10", "source_report_date": "2026-10-14", "value": 100},
        ]
    )
    assert list(panel["value"]) == [100, 112]
    assert list(panel["release_index"]) == [0, 1]


def test_derive_revisions_refuses_to_guess_the_publication_clock():
    """A hub commit is not a Delphi report date; the caller has to say which."""
    frame = pd.DataFrame(
        [{"event_week_end": "2026-10-10", "source_report_date": "2026-10-14", "value": 1}]
    )
    with pytest.raises(PanelContractError):
        derive_revisions(frame, publication_clock="whatever")


def test_derive_revisions_refuses_a_version_without_a_publication_date():
    frame = pd.DataFrame(
        [
            {"source": "nhsn", "signal": "s", "geo_type": "nation", "geo_value": "us",
             "event_week_end": "2026-10-10", "source_report_date": None,
             "value": 1, "vintage_id": "x"}
        ]
    )
    with pytest.raises(PanelContractError):
        derive_revisions(frame, publication_clock="source_report_date")


# ---------------------------------------------------------------------------
# The as-of gate
# ---------------------------------------------------------------------------


def test_as_of_hides_a_version_published_after_the_cut():
    panel = build(
        [
            {"event_week_end": "2026-10-10", "source_report_date": "2026-10-14", "value": 100},
            {"event_week_end": "2026-10-10", "source_report_date": "2026-10-28", "value": 112},
        ]
    )
    visible, status = as_of_view(panel, date(2026, 10, 20), ReplayMode.PUBLIC_REPLAY)
    assert status is Completeness.COMPLETE
    assert len(visible) == 1
    assert visible.iloc[0]["value"] == 100


def test_as_of_returns_the_latest_visible_version_per_key():
    panel = build(
        [
            {"event_week_end": "2026-10-10", "source_report_date": "2026-10-14", "value": 100},
            {"event_week_end": "2026-10-10", "source_report_date": "2026-10-21", "value": 112},
            {"event_week_end": "2026-10-10", "source_report_date": "2026-11-04", "value": 120},
        ]
    )
    visible, _ = as_of_view(panel, date(2026, 10, 30), ReplayMode.PUBLIC_REPLAY)
    assert len(visible) == 1
    assert visible.iloc[0]["value"] == 112


def test_as_of_declines_instead_of_back_filling_when_nothing_is_visible():
    panel = build(
        [{"event_week_end": "2026-10-10", "source_report_date": "2026-10-14", "value": 1}]
    )
    visible, status = as_of_view(panel, date(2026, 10, 1), ReplayMode.PUBLIC_REPLAY)
    assert status is Completeness.INCOMPLETE_HISTORY
    assert visible.empty


def test_observed_replay_also_requires_that_we_actually_fetched_it():
    """A replay of what we saw cannot include a version we never observed."""
    panel = build(
        [{"event_week_end": "2026-10-10", "source_report_date": "2026-10-14", "value": 1}]
    )
    panel.loc[:, "observed_at"] = pd.NaT
    visible, status = as_of_view(panel, date(2026, 10, 20), ReplayMode.OBSERVED_REPLAY)
    assert status is Completeness.INCOMPLETE_HISTORY
    assert visible.empty


def test_eligible_labels_respects_the_declared_maturity_policy():
    panel = build(
        [{"event_week_end": "2026-10-10", "source_report_date": "2026-10-14", "value": 1}]
    )
    assert eligible_labels(panel, date(2026, 11, 1), POLICY).empty
    assert len(eligible_labels(panel, date(2026, 11, 25), POLICY)) == 1


@settings(max_examples=150, deadline=None)
@given(
    offsets=st.lists(st.integers(min_value=0, max_value=400), min_size=1, max_size=12, unique=True),
    weeks=st.lists(st.integers(min_value=0, max_value=20), min_size=1, max_size=4, unique=True),
    cut_offset=st.integers(min_value=-10, max_value=420),
)
def test_no_generated_history_ever_leaks_a_future_publication(offsets, weeks, cut_offset):
    """The invariant is universal, so it is generated rather than exemplified.

    For any history of publications and any cut, nothing the gate returns may
    carry a publication date later than the cut minus the availability margin.
    """
    base = date(2026, 1, 3)
    rows = [
        {
            "event_week_end": str(base + timedelta(weeks=w)),
            "source_report_date": str(base + timedelta(weeks=w, days=o)),
            "value": float(o + w),
        }
        for w in weeks
        for o in offsets
    ]
    panel = build(rows)
    cut = base + timedelta(days=cut_offset)

    visible, status = as_of_view(panel, cut, ReplayMode.PUBLIC_REPLAY)
    if status is not Completeness.COMPLETE:
        assert visible.empty
        return

    cutoff = pd.Timestamp(cut - timedelta(days=AVAILABILITY_MARGIN_DAYS))
    assert (pd.to_datetime(visible["source_report_date"]) <= cutoff).all()
    # And exactly one row per key: a cut describes one state of the world.
    assert not visible.duplicated(subset=["geo_value", "event_week_end"]).any()
