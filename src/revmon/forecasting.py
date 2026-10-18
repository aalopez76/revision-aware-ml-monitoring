"""The forecasts, and the feature contract they are allowed to use.

This is still not a modelling competition — the project's claims are about the
monitoring decision, not predictive accuracy — but a comparison needs something
to compare against, so P2 adds one trainable candidate under a declared recipe.

Candidates reproducible from the as-of state alone:

* `naive` (M0): the last eligible week's value carried forward. Provisional
  Champion, not a presumed winner.
* `seasonal_naive`: the same week one year earlier, only where enough comparable
  history is eligible at the cut.
* `ridge` (M1): a scikit-learn `Pipeline` of `StandardScaler` + `Ridge` over one
  of two **predeclared** feature sets.

**No feature may consume information published after the cut**, which here is
automatic: the input is the frame `load_as_of` returned, and nothing else is
read. Within that frame the distinction still has to be enforced by hand, and it
is the one the project is about:

* **provisional values published before the cut are CONTEXT.** A feature may use
  them, because they were knowable.
* **only MATURE labels may be supervised targets.** Fitting on a value that is
  still being revised is fitting on a moving target.

The loss scale is computed once in a declared calibration window and never
recomputed with later data, because a denominator that moves with the future is
a denominator that can be fitted.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
import pandas as pd

from revmon.temporal import MaturityPolicy

NAIVE = "naive"
SEASONAL_NAIVE = "seasonal_naive"
RIDGE = "ridge"

# --- the two predeclared feature sets --------------------------------------
#
# Two, fixed here before any candidate is scored, because the point of
# predeclaring is that the set cannot be chosen after seeing which one wins.
#
# `F0` is lags plus calendar: the lags were knowable at the cut by construction,
# and the week-of-year encoding is a property of the calendar rather than
# something estimated from the data.
#
# `F1` adds a few backward-only summaries. "Backward-only" is the whole
# contract: a rolling mean that included the target week would be reading the
# answer, and a centred window would read the future.
#
# **Lag 52 is deliberately excluded.** It is computable — the as-of state carries
# event weeks back to 2020 — but the reporting regime changed in 2024, so the
# same week a year earlier is not a comparable observation. Availability is not
# comparability.

F0 = "F0"
F1 = "F1"
FEATURE_SETS = (F0, F1)

LAGS: tuple[int, ...] = (1, 2, 3, 4)
ROLLING_WINDOWS: tuple[int, ...] = (4,)
DIFFERENCES: tuple[int, ...] = (1, 4)
EXCLUDED_LAGS: tuple[int, ...] = (52,)


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


# --- features: backward only, and the boundary is checkable ----------------


def feature_frame(state: pd.DataFrame, *, feature_set: str) -> pd.DataFrame:
    """One row per event week, with features that only look backwards.

    The index is the week the row **predicts**, so a row for week `w` carries
    the value of `w-1`, `w-2`, ... and never `w` itself. Built with `shift`
    before any rolling or differencing, so the target can never leak into its
    own predictors: `rolling(4).mean()` on a shifted series ends at `w-1`.

    The frame runs one week past the last visible one, because that is the week
    a forecast is for. Its `y` is NaN, which is both honest — the label does not
    exist yet — and the mechanism that keeps it out of any fit.

    Raises rather than returning a short frame if the set is unknown, because a
    silently empty feature set would train a model on the calendar alone.
    """
    if feature_set not in FEATURE_SETS:
        raise ForecastError(f"unknown feature set: {feature_set!r}; declared: {FEATURE_SETS}")

    frame = _ordered(state)
    visible = pd.DatetimeIndex(frame["event_week_end"])
    # One slot beyond the last visible week, so the frame also carries the row
    # for the week about to be predicted. Its `y` is NaN by construction, which
    # is what keeps it out of training: `supervised_rows` drops incomplete rows,
    # so the week with no label can never supervise a fit.
    weeks = visible.append(pd.DatetimeIndex([visible[-1] + pd.Timedelta(weeks=1)]))
    value = pd.Series(
        list(frame["value"].astype(float)) + [float("nan")], index=weeks
    )

    # Shift first. Everything downstream is computed from the shifted series, so
    # no window can reach the week it is predicting.
    past = value.shift(1)

    columns: dict[str, pd.Series] = {}
    for lag in LAGS:
        columns[f"lag_{lag}"] = value.shift(lag)

    # Week of year as a smooth pair rather than 53 indicators: the season turns
    # at the year boundary, and an integer week number would put week 52 and
    # week 1 at opposite ends of the range.
    week_of_year = pd.Series(weeks.isocalendar().week.to_numpy(), index=weeks).astype(float)
    columns["season_sin"] = np.sin(2 * np.pi * week_of_year / 52.0)
    columns["season_cos"] = np.cos(2 * np.pi * week_of_year / 52.0)

    if feature_set == F1:
        for window in ROLLING_WINDOWS:
            columns[f"mean_{window}"] = past.rolling(window).mean()
        for span in DIFFERENCES:
            columns[f"diff_{span}"] = value.shift(1) - value.shift(1 + span)

    built = pd.DataFrame(columns, index=weeks)
    built["y"] = value
    return built


def supervised_rows(
    features: pd.DataFrame,
    *,
    decision_as_of: date,
    policy: MaturityPolicy,
    train_from: date,
) -> pd.DataFrame:
    """The rows a model may fit on: complete features and a MATURE target.

    Two filters, and they answer different questions. `train_from` is the
    declared eligible universe — a regime change alters coverage without
    altering the phenomenon, so rows from before it are not the same population.
    The maturity test is about the target only: a provisional value is legitimate
    as a *feature*, because it was published, and illegitimate as a *label*,
    because it is still moving.
    """
    usable = features.dropna()
    if usable.empty:
        return usable
    weeks = [w.date() for w in usable.index]
    keep = [
        w >= train_from and policy.is_eligible(w, decision_as_of) for w in weeks
    ]
    return usable[keep]


def fit_and_forecast_ridge(
    state: pd.DataFrame,
    decision_as_of: date,
    *,
    feature_set: str,
    policy: MaturityPolicy,
    train_from: date,
    min_train_rows: int,
    alpha: float,
) -> Forecast:
    """Fit on mature labels visible at the cut, predict the next week.

    The `Pipeline` is not decoration: it makes the scaler part of the estimator,
    so it is fitted inside this origin's training rows and can never be fitted
    on data the origin had not seen. scikit-learn's own guidance is that
    transformations must only be learnt from the training data; the *temporal*
    half of that is this function's `train_from` and maturity filters, not
    anything scikit-learn can know.

    The prediction row is built from the last weeks **visible** at the cut, which
    may include provisional values. That is deliberate and declared: they were
    published, so they are context.
    """
    from sklearn.linear_model import Ridge as _Ridge
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    if state.empty:
        raise ForecastError("the as-of state is empty; there is nothing to forecast from")

    features = feature_frame(state, feature_set=feature_set)
    training = supervised_rows(
        features, decision_as_of=decision_as_of, policy=policy, train_from=train_from
    )
    if len(training) < min_train_rows:
        raise ForecastError(
            f"{len(training)} supervised rows with a mature target at {decision_as_of}, "
            f"below the declared minimum of {min_train_rows}; this origin is not "
            f"usable by {RIDGE} and is reported as excluded rather than filled in"
        )

    predictors = [c for c in features.columns if c != "y"]
    model = Pipeline(
        [("scale", StandardScaler()), ("ridge", _Ridge(alpha=alpha, random_state=None))]
    )
    model.fit(training[predictors].to_numpy(), training["y"].to_numpy())

    # The row to predict: the week after the last one visible at the cut.
    ordered = _ordered(state)
    last_week = ordered.iloc[-1]["event_week_end"].date()
    target = last_week + timedelta(weeks=1)
    row = features.reindex([pd.Timestamp(target)])[predictors]
    if row.isna().to_numpy().any():
        raise ForecastError(
            f"the feature row for {target} is incomplete at this cut; a forecast is "
            "declined rather than imputed"
        )

    value = float(model.predict(row.to_numpy())[0])
    return Forecast(
        model=f"{RIDGE}_{feature_set}",
        issued_for_cut=str(decision_as_of),
        last_eligible_week=str(last_week),
        target_week=str(target),
        horizon_weeks=(target - last_week).days // 7,
        value=round(value, 6),
        inputs_used=int(len(training)),
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
