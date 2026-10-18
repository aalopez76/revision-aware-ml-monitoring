"""Tests for the temporal contract.

These do not cover lines; they guard decisions. Each one fixes something that,
if it drifted, would invalidate a published result.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from revmon import temporal
from revmon.temporal import (
    AVAILABILITY_MARGIN_DAYS,
    SATURDAY,
    EmissionClass,
    MaturityPolicy,
    ReplayMode,
    TemporalContractError,
    classify_emission,
    lag_days,
    latest_usable_report_date,
    parse_instant,
    parse_report_date,
    parse_week_end,
    target_window,
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


# --- the Saturday convention, now enforced rather than documented -----------


def test_week_end_rejects_a_day_that_is_not_saturday():
    """The source labels weeks by their ending Saturday, so nothing else parses.

    Without this, `target_window` would subtract six days from a Wednesday and
    shift the whole emission classification without anything failing.
    """
    assert parse_week_end("2026-10-17").weekday() == SATURDAY
    for not_a_saturday in ("2026-10-18", "2026-10-16", "2026-10-14"):
        with pytest.raises(TemporalContractError):
            parse_week_end(not_a_saturday)


def test_target_window_is_the_sunday_to_saturday_week_in_utc():
    start, end_exclusive = target_window(date(2026, 10, 17))
    assert start == datetime(2026, 10, 11, tzinfo=UTC)
    assert end_exclusive == datetime(2026, 10, 18, tzinfo=UTC)
    assert start.weekday() == 6  # Sunday
    assert (end_exclusive - start).days == 7


# --- emission class: three values, and a lead that is not one of them -------


def test_emission_before_the_week_opens_is_a_pre_week_forecast():
    """The general contract. This class is reachable; only the +1 recipe is not."""
    emission, lead = classify_emission("2026-10-10T23:59:59+00:00", date(2026, 10, 17))
    assert emission is EmissionClass.PRE_WEEK_FORECAST
    assert lead > 0


def test_lead_is_exactly_zero_at_the_instant_the_week_opens():
    """The boundary that was wrong before: at `target_start` the lead is 0, not negative."""
    emission, lead = classify_emission("2026-10-11T00:00:00+00:00", date(2026, 10, 17))
    assert emission is EmissionClass.INTRA_WEEK_NOWCAST
    assert lead == 0.0


def test_the_last_instant_of_the_week_is_still_a_nowcast():
    emission, lead = classify_emission("2026-10-17T23:59:59+00:00", date(2026, 10, 17))
    assert emission is EmissionClass.INTRA_WEEK_NOWCAST
    assert lead < 0


def test_the_closing_boundary_is_exclusive():
    emission, _ = classify_emission("2026-10-18T00:00:00+00:00", date(2026, 10, 17))
    assert emission is EmissionClass.POST_EVENT


def test_classification_does_not_depend_on_the_offset_it_arrives_in():
    """The same instant written in two timezones must classify identically."""
    utc = classify_emission("2026-10-11T00:00:00+00:00", date(2026, 10, 17))
    shifted = classify_emission("2026-10-10T20:00:00-04:00", date(2026, 10, 17))
    assert utc == shifted


def test_a_naive_emission_instant_is_refused_not_assumed_to_be_utc():
    with pytest.raises(TemporalContractError):
        classify_emission("2026-10-11T00:00:00", date(2026, 10, 17))


# --- the +1 recipe: a property of the scenario, not a rule in the function --


def test_the_plus_one_recipe_can_never_emit_before_the_week_opens():
    """With `W` the last visible week and any lag >= 1 day, pre-week is unreachable.

    The target `W+7` opens on `W+1`, so a pre-week emission would need the cut at
    or before `W`, while the publication lag puts it at `W+lag`. Generated over
    the whole plausible lag range rather than asserted on one example, because
    the claim is about the recipe and not about a date.
    """
    last_visible = date(2026, 1, 3)  # a Saturday
    for lag_in_days in range(1, 61):
        cut = last_visible + timedelta(days=lag_in_days)
        target_week_end = last_visible + timedelta(days=7)
        issued_at = datetime.combine(cut, datetime.min.time(), tzinfo=UTC)
        emission, _ = classify_emission(issued_at, target_week_end)
        assert emission is not EmissionClass.PRE_WEEK_FORECAST, (
            f"lag {lag_in_days} d produced {emission}"
        )


def test_dropping_the_lag_condition_makes_pre_week_reachable_again():
    """The complement of the test above: the impossibility is the recipe's, not the function's.

    A recipe that forecast two weeks out from the same state would emit before
    the target week opened, which is exactly why the constraint must not live
    inside `classify_emission`.
    """
    last_visible = date(2026, 1, 3)
    cut = last_visible + timedelta(days=7)
    two_weeks_out = last_visible + timedelta(days=14)
    emission, lead = classify_emission(
        datetime.combine(cut, datetime.min.time(), tzinfo=UTC), two_weeks_out
    )
    assert emission is EmissionClass.PRE_WEEK_FORECAST
    assert lead > 0


def test_emission_class_and_modality_are_orthogonal():
    """A replay's emission instant is today, so by this clock it is POST_EVENT.

    That is the point of keeping the axes apart: the pair (historical_replay,
    POST_EVENT) is what stops a reconstruction being read as an operation.
    """
    replayed_cut_target = date(2026, 5, 16)
    emission, lead = classify_emission("2026-10-17T01:51:50+00:00", replayed_cut_target)
    assert emission is EmissionClass.POST_EVENT
    assert lead < 0


# --- the scheduled cut: a calendar that does not move with the clock --------


def test_scheduled_cut_is_the_most_recent_saturday():
    """Every day of one week must map to the same cut.

    This guards the defect found on 2026-10-18: cuts were derived from
    `datetime.now()`, so running on a Sunday instead of a Saturday shifted every
    replay origin by a day and issued a second, parallel set of predictions.
    `metodo.md` requires cuts scheduled in advance; a calendar that depends on
    when the job fires is not one.
    """
    saturday = date(2026, 10, 17)
    for offset in range(7):
        day = saturday + timedelta(days=offset)
        assert temporal.scheduled_cut(day) == saturday, f"{day} drifted"
    assert temporal.scheduled_cut(saturday + timedelta(days=7)) == saturday + timedelta(
        days=7
    )


def test_scheduled_cut_always_lands_on_a_saturday():
    start = date(2024, 11, 1)
    for offset in range(0, 740, 13):
        cut = temporal.scheduled_cut(start + timedelta(days=offset))
        assert cut.weekday() == SATURDAY
        assert parse_week_end(cut) == cut  # the stricter parser accepts it


def test_scheduled_cut_is_idempotent():
    """Applying the schedule twice must not move the cut again."""
    for offset in range(0, 30):
        once = temporal.scheduled_cut(date(2026, 10, 1) + timedelta(days=offset))
        assert temporal.scheduled_cut(once) == once
