"""Temporal semantics: seven distinct concepts, four of them observed.

Conflating any two of these is how a look-ahead gets in, so each one is a named
type with a strict parser rather than a string passed around:

| concept              | what it is                                           |
|----------------------|------------------------------------------------------|
| `event_week_end`     | the week the value describes (Saturday week-ending)  |
| `source_report_date` | the publication/ingestion date Delphi V5 declares.   |
|                      | **Day granularity. Not a verified wall-clock hour.** |
| `hub_commit_at`      | when the FluSight hub committed its own copy. A      |
|                      | different channel; it does NOT stand in for the above |
| `observed_at`        | when *this system* fetched and validated a version   |
| `maturity_rule`      | a DECLARED eligibility policy for labels, not an     |
|                      | observed instant                                     |
| `decision_as_of`     | the information cut a decision is made from. A cut,  |
|                      | not another source clock                             |
| `vintage_id`         | identity of a version. **Not a date.**               |

There is deliberately no module-level maturity constant. The previous version of
this project carried `MATURITY_DAYS = 45`, taken from Delphi's documented
behaviour on a *different* series, and that number had started to read as a
property of this target. It is not one: it is a policy that has to be declared,
supplied explicitly, and reported with its sensitivity.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from enum import Enum

# Predeclared grid for the maturity sensitivity analysis. These are not a
# default and no code reads them implicitly: they are the windows the project
# commits in advance to reporting results against, so that the value finally
# used cannot be chosen by looking at the evaluation weeks.
SENSITIVITY_WINDOWS_DAYS: tuple[int, ...] = (45, 60, 90)

# `source_report_date` has day granularity, so "published before the cut" cannot
# be read as "visible at 00:00 of that day". A replay therefore places the cut
# this many days after the declared publication date. Conservative by design:
# claiming intraday visibility that was never demonstrated is the kind of small
# optimism that turns into a look-ahead.
AVAILABILITY_MARGIN_DAYS = 1


class ReplayMode(Enum):
    """Which clock a reconstruction is allowed to rely on."""

    #: Only versions the source declares as published before the cut.
    PUBLIC_REPLAY = "public_replay"
    #: Also requires that this system actually observed them by the cut. Only
    #: exists for cuts where a capture really ran; never back-filled.
    OBSERVED_REPLAY = "observed_replay"
    #: Data fetched, validated and sealed in the current run.
    LIVE = "live"


class Completeness(Enum):
    """Why a reconstruction may not support a decision.

    A monitor that always returns a number is a monitor that invents one. These
    are the ways `load_as_of` is allowed to decline.
    """

    COMPLETE = "complete"
    INCOMPLETE_HISTORY = "incomplete_history"
    DATA_UNAVAILABLE = "data_unavailable"
    INVALID_INPUT = "invalid_input"
    SCHEMA_CHANGED = "schema_changed"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class TemporalContractError(ValueError):
    """An ambiguous or impossible date. Never silently coerced."""


def parse_week_end(value: str | date) -> date:
    """The Saturday week-ending date a row describes.

    Rejects anything that is not an exact `YYYY-MM-DD`; a bare year-week or a
    timestamp would both be guesses about which day is meant.
    """
    if isinstance(value, datetime):
        raise TemporalContractError(f"event_week_end must be a date, got a datetime: {value!r}")
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value).strip(), "%Y-%m-%d").date()
    except ValueError as exc:
        raise TemporalContractError(f"not an unambiguous week-ending date: {value!r}") from exc


def parse_report_date(value: str | date) -> date:
    """A publication date declared by the source, at day granularity.

    Accepts a date or a `YYYY-MM-DD` string. An input carrying a time of day is
    rejected rather than truncated: the project does not get to decide that
    09:00 was the moment a value became public.
    """
    if isinstance(value, datetime):
        raise TemporalContractError(
            f"source_report_date has day granularity; got a timestamp: {value!r}. "
            "Use parse_instant for clocks that really are instants."
        )
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if len(text) != 10:
        raise TemporalContractError(f"not a day-granularity publication date: {value!r}")
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError as exc:
        raise TemporalContractError(f"not a day-granularity publication date: {value!r}") from exc


def parse_instant(value: str | datetime) -> datetime:
    """A real instant, in UTC: a hub commit, or when we observed a version.

    Requires an explicit offset. A naive timestamp is ambiguous, and in this
    project an ambiguous timestamp is a defect rather than something to assume
    is UTC.
    """
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise TemporalContractError(f"instant without timezone: {value!r}")
        return value.astimezone(UTC)
    text = str(value).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise TemporalContractError(f"not an ISO 8601 instant: {value!r}") from exc
    if parsed.tzinfo is None:
        raise TemporalContractError(f"instant without timezone: {value!r}")
    return parsed.astimezone(UTC)


def lag_days(event_week_end: date, publication: date) -> int:
    """Days from the week a value describes to the publication that carried it.

    Negative values are legitimate and are not an error: a nowcast describes a
    week whose data is still arriving.
    """
    return (publication - event_week_end).days


@dataclass(frozen=True)
class MaturityPolicy:
    """A declared rule for when a label may be scored. Supplied, never assumed.

    `days` is the age at which a value becomes eligible. `label_choice` records
    which version is then frozen as the label for that period; taking the first
    eligible publication and keeping it is what stops the scored truth from
    drifting underneath an already-published evaluation.

    Frozen on purpose: a maturity rule that can be reassigned mid-analysis is a
    maturity rule that can be fitted.
    """

    days: int
    label_choice: str = "first_publication_at_or_after_eligibility"
    declared_in: str = "unset"

    def __post_init__(self) -> None:
        if self.days <= 0:
            raise TemporalContractError(f"maturity must be a positive number of days: {self.days}")
        if self.declared_in == "unset":
            raise TemporalContractError(
                "a maturity policy has to say where it was declared (a frozen act, "
                "a config file, or the development run that fixed it). An undeclared "
                "policy is indistinguishable from one chosen after seeing results."
            )

    def eligible_from(self, event_week_end: date) -> date:
        """First date on which this period's label may be scored."""
        return event_week_end + timedelta(days=self.days)

    def is_eligible(self, event_week_end: date, as_of: date) -> bool:
        """Whether this period's label may be scored at `as_of`. Inclusive."""
        return as_of >= self.eligible_from(event_week_end)


def latest_usable_report_date(decision_as_of: date, mode: ReplayMode) -> date:
    """The newest publication date a cut is allowed to see.

    In `PUBLIC_REPLAY` the day-granularity margin applies, so a value published
    on the cut date itself does not count as having been available. `LIVE` and
    `OBSERVED_REPLAY` are bounded by what was actually fetched, which is checked
    against `observed_at` rather than inferred here.
    """
    if mode is ReplayMode.PUBLIC_REPLAY:
        return decision_as_of - timedelta(days=AVAILABILITY_MARGIN_DAYS)
    return decision_as_of
