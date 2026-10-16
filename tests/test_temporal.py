"""Tests for the temporal contract.

These do not cover lines; they guard decisions. Each one fixes something that,
if it drifted, would invalidate a published result.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from revmon import temporal
from revmon.temporal import (
    AVAILABILITY_MARGIN_DAYS,
    MaturityPolicy,
    ReplayMode,
    TemporalContractError,
    lag_days,
    latest_usable_report_date,
    parse_instant,
    parse_report_date,
    parse_week_end,
)


def test_lag_is_days_from_event_week_to_publication():
    assert lag_days(date(2026, 10, 10), date(2026, 10, 14)) == 4


def test_negative_lag_is_allowed_not_an_error():
    """A nowcast describes a week whose data is still arriving."""
    assert lag_days(date(2026, 10, 17), date(2026, 10, 14)) == -3


def test_maturity_boundary_is_inclusive():
    policy = MaturityPolicy(days=45, declared_in="test")
    week = date(2026, 1, 3)
    assert policy.eligible_from(week) == date(2026, 2, 17)
    assert policy.is_eligible(week, date(2026, 2, 17))
    assert not policy.is_eligible(week, date(2026, 2, 16))


def test_maturity_policy_must_say_where_it_was_declared():
    """An undeclared policy cannot be told apart from one chosen afterwards."""
    with pytest.raises(TemporalContractError):
        MaturityPolicy(days=45)


def test_maturity_policy_rejects_nonsense_windows():
    with pytest.raises(TemporalContractError):
        MaturityPolicy(days=0, declared_in="test")


def test_there_is_no_module_level_maturity_default():
    """The successor to the old `MATURITY_DAYS = 45`.

    That constant came from Delphi's documented behaviour on a *different*
    series and had started to read as a property of this target. Maturity is a
    policy the caller declares; a module-level default would let it be inherited
    silently again.
    """
    assert not hasattr(temporal, "MATURITY_DAYS")
    assert temporal.SENSITIVITY_WINDOWS_DAYS == (45, 60, 90)


def test_week_end_parsing_is_strict():
    assert parse_week_end("2026-10-10") == date(2026, 10, 10)
    with pytest.raises(TemporalContractError):
        parse_week_end("2026-W41")
    with pytest.raises(TemporalContractError):
        parse_week_end(datetime(2026, 10, 10, 12, 0, tzinfo=UTC))


def test_report_date_refuses_a_timestamp_rather_than_truncating_it():
    """`source_report_date` has day granularity.

    Accepting a timestamp and dropping the time would be this project asserting
    that it knows the hour a value became public. It does not.
    """
    assert parse_report_date("2026-10-14") == date(2026, 10, 14)
    with pytest.raises(TemporalContractError):
        parse_report_date("2026-10-14T19:21:00Z")
    with pytest.raises(TemporalContractError):
        parse_report_date(datetime(2026, 10, 14, 19, 21, tzinfo=UTC))


def test_instant_requires_an_explicit_offset():
    assert parse_instant("2026-10-14T19:21:00Z") == datetime(
        2026, 10, 14, 19, 21, tzinfo=UTC
    )
    with pytest.raises(TemporalContractError):
        parse_instant("2026-10-14T19:21:00")


def test_public_replay_applies_the_availability_margin():
    """A same-day publication does not count as having been visible."""
    cut = date(2026, 10, 14)
    public = latest_usable_report_date(cut, ReplayMode.PUBLIC_REPLAY)
    assert (cut - public).days == AVAILABILITY_MARGIN_DAYS
    assert latest_usable_report_date(cut, ReplayMode.LIVE) == cut
