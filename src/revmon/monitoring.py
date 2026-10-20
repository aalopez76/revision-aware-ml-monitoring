"""Signals, the information ablation, and a recommendation that is not an act.

The monitor turns an as-of state into one of five recommendations. It never
deploys, promotes or retrains anything: a recommendation to evaluate retraining
is a proposal for a human, and the distance between those two is most of what
this project is about.

Six signal types, kept apart on purpose, because collapsing them is the mistake
being measured:

* `DATA_QUALITY` — structure, missingness, duplication, consistency
* `DATA_COVERAGE` — how much of the reporting population is present
* `DATA_REVISION` — an already-published observation was restated
* `PERFORMANCE` — error moved, measured on labels eligible under the policy
* `PIPELINE_HEALTH` — a capture or a run failed
* `INSUFFICIENT_EVIDENCE` — the window is too short or too provisional

`CONCEPT_DRIFT` is **not** in that list and is never emitted. It remains a
possible explanation for what the others do not account for, named as such.

The rule table is a declared precedence, not a scoring function, so that the
reason behind a recommendation can always be stated in one line. Thresholds are
development values until the freeze; they are recorded in the run's config so
that what produced a recommendation is never in doubt.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import pandas as pd

from revmon.forecasting import LossScale, scaled_loss
from revmon.temporal import Completeness, MaturityPolicy

# --- the five admissible recommendations -----------------------------------

CONTINUE = "CONTINUAR"
WAIT_FOR_MATURITY = "ESPERAR_MADUREZ"
INVESTIGATE_DATA = "INVESTIGAR_DATO"
EVALUATE_RETRAINING = "EVALUAR_REENTRENO"
ABSTAIN = "ABSTENERSE"

ACTIONS = (CONTINUE, WAIT_FOR_MATURITY, INVESTIGATE_DATA, EVALUATE_RETRAINING, ABSTAIN)

# --- signal types -----------------------------------------------------------

DATA_QUALITY = "DATA_QUALITY"
DATA_COVERAGE = "DATA_COVERAGE"
DATA_REVISION = "DATA_REVISION"
PERFORMANCE = "PERFORMANCE"
PIPELINE_HEALTH = "PIPELINE_HEALTH"
INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


@dataclass(frozen=True)
class Information:
    """One cell of the 2x2: which information the rule may use.

    The arms are crossed rather than chained because a sequential ablation
    measures the contribution of coverage *conditional on* revisions having been
    added first, and that number depends on the order chosen.
    """

    revision: bool
    coverage: bool

    @property
    def arm(self) -> str:
        return f"d_{int(self.revision)}{int(self.coverage)}"


ARMS = (
    Information(revision=False, coverage=False),
    Information(revision=True, coverage=False),
    Information(revision=False, coverage=True),
    Information(revision=True, coverage=True),
)


@dataclass(frozen=True)
class Thresholds:
    """Declared in development, frozen before the confirmatory cohort.

    `declared_in` is required for the same reason the maturity policy requires
    it: a threshold with no provenance cannot be told apart from one chosen
    after seeing the four discordance rates.
    """

    loss_alarm: float
    revision_share_alarm: float
    coverage_drop_alarm: float
    min_mature_labels: int
    declared_in: str

    def as_dict(self) -> dict:
        return {
            "loss_alarm": self.loss_alarm,
            "revision_share_alarm": self.revision_share_alarm,
            "coverage_drop_alarm": self.coverage_drop_alarm,
            "min_mature_labels": self.min_mature_labels,
            "declared_in": self.declared_in,
        }


@dataclass
class Signal:
    kind: str
    value: float | None
    detail: str

    def as_dict(self) -> dict:
        return {"kind": self.kind, "value": self.value, "detail": self.detail}


@dataclass
class Recommendation:
    action: str
    reason: str
    arm: str
    signals: list[Signal] = field(default_factory=list)
    evidence: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "action": self.action,
            "reason": self.reason,
            "arm": self.arm,
            "signals": [s.as_dict() for s in self.signals],
            "evidence": self.evidence,
        }


def recent_loss(
    state: pd.DataFrame,
    predictions: pd.DataFrame,
    scale: LossScale,
    policy: MaturityPolicy,
    decision_as_of: date,
) -> tuple[float | None, int]:
    """Mean scaled loss over labels eligible at the cut, and how many there were.

    Returns `(None, 0)` rather than a number when nothing is eligible. A monitor
    that always produces a figure is a monitor that invents one, and an immature
    label scored as if it were final is the second way a look-ahead enters.
    """
    if predictions.empty or state.empty:
        return None, 0

    truth = state.copy()
    truth["event_week_end"] = pd.to_datetime(truth["event_week_end"])
    truth = truth[["event_week_end", "value"]].rename(columns={"value": "y_true"})

    # Predictions are stored as text, which is what makes them inspectable and
    # immutable on disk; the week is parsed here rather than on the way in, so a
    # stored forecast is never rewritten in a different shape.
    issued = predictions.copy()
    issued["target_week"] = pd.to_datetime(issued["target_week"])

    joined = issued.merge(
        truth, left_on="target_week", right_on="event_week_end", how="inner"
    )
    if joined.empty:
        return None, 0

    weeks = pd.to_datetime(joined["target_week"]).dt.date
    eligible = joined[[policy.is_eligible(w, decision_as_of) for w in weeks]]
    if eligible.empty:
        return None, 0

    losses = [
        scaled_loss(row.y_true, row.y_pred, scale) for row in eligible.itertuples()
    ]
    return round(sum(losses) / len(losses), 6), len(losses)


def revision_share(
    state_history: pd.DataFrame,
    lookback_weeks: int = 8,
    *,
    anchor_week: date | None = None,
) -> float | None:
    """Share of recent comparable publication pairs whose value changed.

    The denominator is pairs in which the key appeared on both sides, which is
    what G0 measured to be the right definition: `/archive/` keeps unchanged
    republications but a key is absent from most publications, so dividing by
    the rows the endpoint returned would be dividing by the wrong thing.

    `anchor_week` names where the window ends, and the caller has to name it for
    the same reason `derive_revisions` refuses to guess a clock. Left at `None`
    the window ends at the newest event week present — the edge of the series,
    which every release restates, so the signal measures the edge being fresh
    rather than anything having gone unusually wrong. Given a week, the window
    ends there, which is how this signal can be put at the same lag as coverage.
    """
    if state_history.empty:
        return None
    frame = state_history.copy()
    frame["event_week_end"] = pd.to_datetime(frame["event_week_end"])
    if anchor_week is not None:
        frame = frame[frame["event_week_end"] <= pd.Timestamp(anchor_week)]
        if frame.empty:
            return None
    cutoff = frame["event_week_end"].max() - pd.Timedelta(weeks=lookback_weeks)
    recent = frame[frame["event_week_end"] >= cutoff]
    pairs = recent[~recent["is_first_release"].astype(bool)]
    if pairs.empty:
        return None
    return round(float(pairs["revised"].astype(bool).mean()), 6)


def coverage_drop(
    coverage: pd.DataFrame | None,
    lookback_weeks: int = 4,
    *,
    anchor_week: date | None = None,
) -> float | None:
    """Fall in reporting coverage against its recent level, in percentage points.

    A jump in admissions can come from more hospitals reporting. That is neither
    a revision nor a change in the phenomenon, and it is measurable from the
    source, which is why it is a signal here and not a caveat in a footnote.

    `anchor_week` works exactly as it does in `revision_share`, and for the same
    reason: the newest coverage week at a cut is the least completely reported
    one, so an unanchored reading of this signal is dominated by that edge. The
    two signals have to be anchored alike or the 2x2 crosses a measurement of
    the edge with a measurement of the data.
    """
    if coverage is None or coverage.empty:
        return None
    frame = coverage.copy()
    frame["event_week_end"] = pd.to_datetime(frame["event_week_end"])
    frame = frame.sort_values("event_week_end")
    if anchor_week is not None:
        frame = frame[frame["event_week_end"] <= pd.Timestamp(anchor_week)]
    if len(frame) < 2:
        return None
    latest = float(frame.iloc[-1]["value"])
    baseline = float(frame.iloc[-(lookback_weeks + 1) : -1]["value"].mean())
    return round(baseline - latest, 6)


def recommend(
    *,
    information: Information,
    thresholds: Thresholds,
    completeness: Completeness,
    loss: float | None,
    mature_labels: int,
    revisions: float | None,
    coverage_fall: float | None,
    pipeline_ok: bool = True,
) -> Recommendation:
    """Apply the declared precedence and say which rule fired.

    The order is the rule: a data or process failure never becomes "the model
    degraded", and an alarm with no eligible label never becomes a performance
    claim.
    """
    signals: list[Signal] = []
    if revisions is not None and information.revision:
        signals.append(Signal(DATA_REVISION, revisions, f"{revisions:.1%} of recent pairs revised"))
    if coverage_fall is not None and information.coverage:
        signals.append(
            Signal(DATA_COVERAGE, coverage_fall, f"{coverage_fall:+.2f} points against baseline")
        )
    if loss is not None:
        signals.append(Signal(PERFORMANCE, loss, f"mean scaled loss over {mature_labels} labels"))

    evidence = {
        "loss": loss,
        "mature_labels": mature_labels,
        "revision_share": revisions,
        "coverage_drop": coverage_fall,
        "completeness": completeness.value,
        "information": {"revision": information.revision, "coverage": information.coverage},
    }

    def done(action: str, reason: str) -> Recommendation:
        return Recommendation(action, reason, information.arm, signals, evidence)

    if not pipeline_ok:
        signals.append(Signal(PIPELINE_HEALTH, None, "the run did not complete"))
        return done(ABSTAIN, "a failed run is not evidence about the model")

    if completeness is not Completeness.COMPLETE:
        signals.append(Signal(INSUFFICIENT_EVIDENCE, None, completeness.value))
        return done(ABSTAIN, f"the as-of state is {completeness.value}")

    if loss is None or mature_labels < thresholds.min_mature_labels:
        signals.append(Signal(INSUFFICIENT_EVIDENCE, mature_labels, "not enough eligible labels"))
        return done(
            WAIT_FOR_MATURITY,
            f"{mature_labels} eligible labels, below the declared minimum of "
            f"{thresholds.min_mature_labels}",
        )

    # Data first. A restated record or a coverage fall is a reason to look at the
    # data before concluding anything about the model — and only the arms that
    # hold that information may act on it, which is what the ablation measures.
    if (
        information.revision
        and revisions is not None
        and revisions > thresholds.revision_share_alarm
    ):
        return done(
            INVESTIGATE_DATA,
            f"{revisions:.1%} of recent comparable pairs were revised, above the "
            f"declared {thresholds.revision_share_alarm:.0%}",
        )
    if (
        information.coverage
        and coverage_fall is not None
        and coverage_fall > thresholds.coverage_drop_alarm
    ):
        return done(
            INVESTIGATE_DATA,
            f"reporting coverage fell {coverage_fall:.2f} points, above the declared "
            f"{thresholds.coverage_drop_alarm}",
        )

    if loss > thresholds.loss_alarm:
        return done(
            EVALUATE_RETRAINING,
            f"mean scaled loss {loss:.3f} over {mature_labels} eligible labels, above "
            f"the declared alarm at {thresholds.loss_alarm}",
        )

    return done(CONTINUE, f"mean scaled loss {loss:.3f} is within the declared alarm")
