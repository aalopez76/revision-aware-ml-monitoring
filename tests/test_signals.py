"""The two information signals: where their window ends, and what saturates.

G2-A measured that the revised *share* is 1.0 for all 1046 comparable pairs in
the development triangle, at every publication lag out past 180 days. These
tests pin down the three things that finding rests on, so it is a property of
stated logic and not an observation about one download:

* `visible_triangle` is the same visibility rule as `as_of_view`, not a second
  one — a monitor and a forecaster must disagree about *shape*, never about what
  was knowable;
* a saturated share and a varying magnitude are logically independent, which is
  what makes replacing the first with the second a change of signal rather than
  a rescaling of the same one;
* both signals accept an explicit window anchor, and leaving it out reproduces
  exactly what the G1 chain computed, so the sealed artefact stays reproducible.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from revmon.monitoring import coverage_drop, revision_share
from revmon.panel import as_of_view, derive_revisions, visible_triangle
from revmon.temporal import ReplayMode

ROOT_DIR = Path(__file__).resolve().parents[1]


def build(rows: list[dict]) -> pd.DataFrame:
    """A triangle from terse rows, with the identity columns defaulted."""
    frame = pd.DataFrame(rows)
    frame["source"] = "nhsn"
    frame["signal"] = "confirmed_admissions_flu_ew"
    frame["geo_type"] = "nation"
    frame["geo_value"] = "us"
    frame["fill_method"] = "source"
    frame["vintage_id"] = frame["source_report_date"].astype(str)
    frame["observed_at"] = pd.to_datetime(frame["source_report_date"], utc=True)
    return derive_revisions(frame, publication_clock="source_report_date")


def coverage_series(values: list[float]) -> pd.DataFrame:
    weeks = pd.date_range("2025-01-04", periods=len(values), freq="7D")
    return pd.DataFrame({"event_week_end": weeks, "value": values})


def diagnostics():
    """The G2-A script, loaded as a module so its helpers can be tested."""
    spec = importlib.util.spec_from_file_location(
        "signal_diagnostics", ROOT_DIR / "scripts" / "02_signal_diagnostics.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# --- one definition of visibility, two shapes ------------------------------


def test_the_triangle_keeps_every_version_and_the_view_keeps_one():
    """The whole reason `visible_triangle` exists: collapsing deletes the signal."""
    panel = build([
        {"event_week_end": "2025-01-04", "source_report_date": "2025-01-08", "value": 100},
        {"event_week_end": "2025-01-04", "source_report_date": "2025-01-15", "value": 110},
        {"event_week_end": "2025-01-04", "source_report_date": "2025-01-22", "value": 112},
    ])
    cut = date(2025, 2, 1)

    triangle = visible_triangle(panel, cut, ReplayMode.PUBLIC_REPLAY)
    view, _ = as_of_view(panel, cut, ReplayMode.PUBLIC_REPLAY)

    assert len(triangle) == 3, "a monitor needs the versions themselves"
    assert len(view) == 1, "a forecaster needs one value per week"
    assert float(view.iloc[0]["value"]) == 112.0


def test_a_version_published_after_the_cut_is_in_neither():
    """Stated as an agreement between the two, so they cannot drift apart."""
    panel = build([
        {"event_week_end": "2025-01-04", "source_report_date": "2025-01-08", "value": 100},
        {"event_week_end": "2025-01-04", "source_report_date": "2025-03-01", "value": 999},
    ])
    cut = date(2025, 1, 20)

    triangle = visible_triangle(panel, cut, ReplayMode.PUBLIC_REPLAY)
    view, _ = as_of_view(panel, cut, ReplayMode.PUBLIC_REPLAY)

    assert 999.0 not in set(triangle["value"].astype(float))
    assert float(view.iloc[0]["value"]) == 100.0
    assert set(pd.to_datetime(triangle["source_report_date"]).dt.date) == {date(2025, 1, 8)}


def test_live_mode_takes_the_frame_as_given():
    panel = build([
        {"event_week_end": "2025-01-04", "source_report_date": "2025-03-01", "value": 7},
    ])
    assert len(visible_triangle(panel, date(2025, 1, 5), ReplayMode.LIVE)) == 1


# --- a saturated share and a varying magnitude are different quantities ----


def test_the_share_can_saturate_while_the_magnitude_varies():
    """The logical independence the G2-A finding rests on.

    Every pair here was revised, so the share is 1.0 and discriminates nothing.
    The sizes differ by two orders of magnitude, so a magnitude signal still
    separates these weeks. Without this, "replace the share with the magnitude"
    would only be an observation about one download.
    """
    panel = build([
        {"event_week_end": "2025-01-04", "source_report_date": "2025-01-08", "value": 1000},
        {"event_week_end": "2025-01-04", "source_report_date": "2025-01-15", "value": 1001},
        {"event_week_end": "2025-01-11", "source_report_date": "2025-01-15", "value": 1000},
        {"event_week_end": "2025-01-11", "source_report_date": "2025-01-22", "value": 1300},
    ])
    assert revision_share(panel, lookback_weeks=8) == 1.0

    module = diagnostics()
    pairs = panel[~panel["is_first_release"].astype(bool)]
    relative = module.relative_revisions(pairs)
    assert round(float(relative.min()), 6) == 0.001
    assert round(float(relative.max()), 6) == 0.3


def test_a_zero_base_pair_is_dropped_rather_than_divided_by():
    """There is no relative change from nothing, and substituting one invents it."""
    panel = build([
        {"event_week_end": "2025-01-04", "source_report_date": "2025-01-08", "value": 0},
        {"event_week_end": "2025-01-04", "source_report_date": "2025-01-15", "value": 50},
        {"event_week_end": "2025-01-11", "source_report_date": "2025-01-15", "value": 200},
        {"event_week_end": "2025-01-11", "source_report_date": "2025-01-22", "value": 220},
    ])
    module = diagnostics()
    pairs = panel[~panel["is_first_release"].astype(bool)]
    relative = module.relative_revisions(pairs)

    assert len(relative) == 1, "the pair restating a zero must not contribute"
    assert round(float(relative.iloc[0]), 6) == 0.1


def test_the_denominator_is_the_value_that_was_replaced():
    """Not the restated one: a monitor compares against what it was looking at."""
    panel = build([
        {"event_week_end": "2025-01-04", "source_report_date": "2025-01-08", "value": 200},
        {"event_week_end": "2025-01-04", "source_report_date": "2025-01-15", "value": 250},
    ])
    module = diagnostics()
    pairs = panel[~panel["is_first_release"].astype(bool)]
    relative = module.relative_revisions(pairs)
    # 50/200 = 0.25 against the replaced value; 50/250 = 0.20 against the new one.
    assert round(float(relative.iloc[0]), 6) == 0.25


def test_the_magnitude_needs_an_anchor_and_says_so():
    module = diagnostics()
    panel = build([
        {"event_week_end": "2025-01-04", "source_report_date": "2025-01-08", "value": 100},
        {"event_week_end": "2025-01-04", "source_report_date": "2025-01-15", "value": 110},
    ])
    assert module.revision_magnitude_at_cut(panel, 8, None) == (None, None)
    assert module.revision_magnitude_at_cut(panel.iloc[0:0], 8, date(2025, 1, 4)) == (None, None)


# --- the anchor, and the G1 behaviour preserved when it is absent ----------


def test_no_anchor_reproduces_what_the_g1_chain_computed():
    """A regression lock on a sealed artefact: G1's figure must not move."""
    panel = build([
        {"event_week_end": "2025-01-04", "source_report_date": "2025-01-08", "value": 100},
        {"event_week_end": "2025-01-04", "source_report_date": "2025-01-15", "value": 100},
        {"event_week_end": "2025-01-11", "source_report_date": "2025-01-15", "value": 200},
        {"event_week_end": "2025-01-11", "source_report_date": "2025-01-22", "value": 260},
    ])
    # Two comparable pairs in the window, one of them revised.
    assert revision_share(panel, lookback_weeks=8) == 0.5


def test_an_anchor_excludes_the_edge_that_the_default_includes():
    """The two anchorings have to be able to disagree, or contrasting them is empty."""
    panel = build([
        {"event_week_end": "2025-01-04", "source_report_date": "2025-01-08", "value": 100},
        {"event_week_end": "2025-01-04", "source_report_date": "2025-01-15", "value": 100},
        {"event_week_end": "2025-01-11", "source_report_date": "2025-01-15", "value": 200},
        {"event_week_end": "2025-01-11", "source_report_date": "2025-01-22", "value": 260},
    ])
    assert revision_share(panel, lookback_weeks=8) == 0.5
    # Anchored before the restated week, the only remaining pair is unchanged.
    assert revision_share(panel, lookback_weeks=8, anchor_week=date(2025, 1, 4)) == 0.0


def test_an_anchor_before_the_whole_frame_is_missing_not_zero():
    """An absent signal is not a quiet one, so it must not come back as 0.0."""
    panel = build([
        {"event_week_end": "2025-01-11", "source_report_date": "2025-01-15", "value": 200},
        {"event_week_end": "2025-01-11", "source_report_date": "2025-01-22", "value": 260},
    ])
    assert revision_share(panel, lookback_weeks=8, anchor_week=date(2024, 12, 1)) is None


def test_coverage_anchored_at_the_edge_and_before_it_differ():
    """The same defect on the other factor: the newest week is the least reported."""
    # A flat level, then an under-reported newest week.
    frame = coverage_series([90.0, 90.0, 90.0, 90.0, 80.0])
    edge = coverage_drop(frame, lookback_weeks=4)
    assert edge == pytest.approx(10.0), "unanchored, the signal is the edge"

    anchored = coverage_drop(frame, lookback_weeks=4, anchor_week=date(2025, 1, 18))
    assert anchored == pytest.approx(0.0), "anchored before it, there is no fall"


def test_coverage_anchored_too_early_is_missing_not_zero():
    frame = coverage_series([90.0, 90.0, 90.0])
    assert coverage_drop(frame, anchor_week=date(2025, 1, 4)) is None
