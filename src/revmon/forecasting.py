"""The forecast, kept deliberately small.

This is not a modelling competition. The forecast exists so that there is
something to monitor, and the project's claims are about the monitoring
decision, not about predictive accuracy. A richer model would add tuning
decisions that would then have to be frozen, documented and defended, and would
buy nothing for the question being asked.

Two baselines, both reproducible from the as-of state alone:

* `naive`: the last eligible week's value carried forward.
* `seasonal_naive`: the same week one year earlier, used only where enough
  comparable history is eligible at the cut.

**No feature may consume information published after the cut**, which here is
automatic: the input is the frame `load_as_of` returned, and nothing else is
read. The loss scale is computed once in a declared calibration window and never
recomputed with later data, because a denominator that moves with the future is
a denominator that can be fitted.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd

from revmon.temporal import MaturityPolicy

NAIVE = "naive"
SEASONAL_NAIVE = "seasonal_naive"


class ForecastError(ValueError):
    """The as-of state does not support a forecast. Never silently patched."""


@dataclass(frozen=True)
class Forecast:
    """One point forecast, and everything needed to reproduce it.

    `horizon_weeks` is recorded in weeks rather than implied by a label like
    "one week ahead": if a publication arrives late the last eligible week is
    older, so the distance from the cut to the target varies, and a loss average
    that mixed horizons would bias any comparison between policies that retrain
    at different moments.
    """

    model: str
    issued_for_cut: str
    last_eligible_week: str
    target_week: str
    horizon_weeks: int
    value: float
    inputs_used: int

    def as_dict(self) -> dict:
        return {
            "model": self.model,
            "issued_for_cut": self.issued_for_cut,
            "last_eligible_week": self.last_eligible_week,
            "target_week": self.target_week,
            "horizon_weeks": self.horizon_weeks,
            "y_pred": self.value,
            "inputs_used": self.inputs_used,
        }


def _ordered(state: pd.DataFrame) -> pd.DataFrame:
    frame = state.copy()
    frame["event_week_end"] = pd.to_datetime(frame["event_week_end"])
    return frame.sort_values("event_week_end").reset_index(drop=True)


def forecast(state: pd.DataFrame, decision_as_of: date, *, model: str = NAIVE) -> Forecast:
    """A forecast for the week after the last one visible at the cut."""
    if state.empty:
        raise ForecastError("the as-of state is empty; there is nothing to forecast from")

    frame = _ordered(state)
    last = frame.iloc[-1]
    last_week = last["event_week_end"].date()
    target = last_week + timedelta(weeks=1)
    horizon = (target - last_week).days // 7

    if model == NAIVE:
        value = float(last["value"])
    elif model == SEASONAL_NAIVE:
        a_year_back = pd.Timestamp(target - timedelta(weeks=52))
        match = frame[frame["event_week_end"] == a_year_back]
        if match.empty:
            raise ForecastError(
                f"seasonal naive needs the week ending {a_year_back.date()}, which is "
                "not eligible at this cut; use the naive baseline and say so"
            )
        value = float(match.iloc[-1]["value"])
    else:
        raise ForecastError(f"unknown model: {model!r}")

    return Forecast(
        model=model,
        issued_for_cut=str(decision_as_of),
        last_eligible_week=str(last_week),
        target_week=str(target),
        horizon_weeks=horizon,
        value=value,
        inputs_used=int(len(frame)),
    )


@dataclass(frozen=True)
class LossScale:
    """The fixed denominator of the scaled loss, and where it came from.

    Declared and frozen on purpose: the same `s_dev` is used for every policy
    and every period, and it is never recomputed with data the evaluation had
    not seen. Publishing it, its window and the number of pairs behind it is
    what lets a reader check it was not chosen to flatter a result.
    """

    s_dev: float
    window_from: str
    window_to: str
    pairs: int
    method: str = "mean absolute week-over-week difference of eligible labels"

    def as_dict(self) -> dict:
        return {
            "s_dev": self.s_dev,
            "window_from": self.window_from,
            "window_to": self.window_to,
            "pairs": self.pairs,
            "method": self.method,
        }


def calibrate_scale(
    state: pd.DataFrame,
    *,
    window_from: date,
    window_to: date,
    policy: MaturityPolicy,
) -> LossScale:
    """Compute `s_dev` once, in a declared retrospective window.

    Falls back to nothing: if a positive scale cannot be computed, it raises, and
    the predefined fallback to an absolute loss is the caller's declared choice
    rather than a silent substitution here.
    """
    frame = _ordered(state)
    weeks = frame["event_week_end"].dt.date
    # Wrapped in a Series on purpose: combining a boolean Series with a plain
    # list is no longer allowed, and the version that silently worked would have
    # been a mask applied in the wrong order.
    mature = pd.Series([policy.is_eligible(w, window_to) for w in weeks], index=frame.index)
    eligible = frame[(weeks >= window_from) & (weeks <= window_to) & mature]
    diffs = eligible["value"].astype(float).diff().abs().dropna()
    if diffs.empty or float(diffs.mean()) <= 0:
        raise ForecastError(
            "no positive loss scale available in the declared calibration window; "
            "use the predefined absolute-loss fallback and report its units"
        )
    return LossScale(
        s_dev=round(float(diffs.mean()), 6),
        window_from=str(window_from),
        window_to=str(window_to),
        pairs=int(len(diffs)),
    )


def scaled_loss(y_true: float, y_pred: float, scale: LossScale) -> float:
    """Absolute error in units of the declared scale."""
    return abs(float(y_true) - float(y_pred)) / scale.s_dev
