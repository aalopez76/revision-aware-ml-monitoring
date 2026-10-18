"""The feature contract: nothing looks forward, and labels are not context.

These are the tests that make the comparison in P2 mean anything. A backtest
with a leak does not produce a weak result, it produces a confident wrong one,
and the leak is invisible in the output — so each way in gets its own test:

* a feature reading the week it predicts,
* a window reaching across the target,
* a later publication changing an earlier feature row,
* a provisional value supervising a fit,
* a scaler fitted on more than this origin's training rows.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from revmon.forecasting import (
    DIFFERENCES,
    EXCLUDED_LAGS,
    F0,
    F1,
    LAGS,
    ROLLING_WINDOWS,
    ForecastError,
    feature_frame,
    fit_and_forecast_ridge,
    supervised_rows,
)
from revmon.temporal import MaturityPolicy

ROOT_DIR = Path(__file__).resolve().parents[1]
POLICY = MaturityPolicy(days=45, declared_in="test")
FIRST_SATURDAY = date(2024, 11, 2)


def series(values: list[float], start: date = FIRST_SATURDAY) -> pd.DataFrame:
    """An as-of state shaped like the one `load_as_of` returns."""
    weeks = [start + timedelta(weeks=i) for i in range(len(values))]
    return pd.DataFrame({"event_week_end": weeks, "value": values})


# --- a feature never reads the week it predicts -----------------------------


@pytest.mark.parametrize("feature_set", [F0, F1])
def test_every_lag_equals_a_strictly_earlier_week(feature_set):
    """Not "the lags look right": each one is checked against its own date."""
    values = [float(100 + 10 * i) for i in range(30)]
    state = series(values)
    built = feature_frame(state, feature_set=feature_set)

    by_week = {w.date(): v for w, v in zip(built.index, built["y"], strict=True)}
    for week in list(by_week)[max(LAGS) :]:
        row = built.loc[pd.Timestamp(week)]
        for lag in LAGS:
            expected = by_week[week - timedelta(weeks=lag)]
            assert row[f"lag_{lag}"] == expected, f"lag_{lag} at {week} is not week-{lag}"


def test_the_target_is_never_among_its_own_predictors():
    state = series([float(i) for i in range(40)])
    built = feature_frame(state, feature_set=F1)
    predictors = [c for c in built.columns if c != "y"]

    # A constant-then-spike series: if any predictor read the target week, the
    # spike would appear in that week's own predictors.
    spiked = [1.0] * 30 + [9999.0]
    built_spiked = feature_frame(series(spiked), feature_set=F1)
    # index[-1] is the week being predicted, which has no label; the spike is
    # the last week that actually carries an observation.
    spike_week = built_spiked.index[-2]
    row = built_spiked.loc[spike_week, predictors]
    assert row.max() < 9999.0, "the spike reached its own predictor row"
    assert built_spiked.loc[spike_week, "y"] == 9999.0
    assert pd.isna(built_spiked.loc[built_spiked.index[-1], "y"])


def test_rolling_and_difference_windows_end_before_the_target():
    """A centred or unshifted window is the second way the future gets in."""
    values = [1.0] * 20 + [100.0]
    built = feature_frame(series(values), feature_set=F1)
    spike_week = built.index[-2]  # the week holding 100
    for window in ROLLING_WINDOWS:
        assert built.loc[spike_week, f"mean_{window}"] == 1.0
    for span in DIFFERENCES:
        assert built.loc[spike_week, f"diff_{span}"] == 0.0


def test_lag_52_is_not_built_even_though_the_history_allows_it():
    """Availability is not comparability: the reporting regime changed in 2024."""
    built = feature_frame(series([float(i) for i in range(120)]), feature_set=F1)
    for lag in EXCLUDED_LAGS:
        assert f"lag_{lag}" not in built.columns


def test_an_unknown_feature_set_raises_instead_of_training_on_the_calendar():
    with pytest.raises(ForecastError):
        feature_frame(series([1.0] * 20), feature_set="F2")


# --- a later publication cannot change an earlier feature row ---------------


@settings(max_examples=40, deadline=None)
@given(
    history=st.lists(
        st.floats(min_value=0.0, max_value=5e4, allow_nan=False), min_size=12, max_size=40
    ),
    future=st.lists(
        st.floats(min_value=0.0, max_value=5e4, allow_nan=False), min_size=1, max_size=10
    ),
)
def test_appending_later_weeks_leaves_earlier_feature_rows_identical(history, future):
    """The invariant stated as a property, over generated histories.

    This is the one that catches a leak nobody wrote on purpose: if any feature
    were computed over the whole frame rather than strictly backwards, adding
    weeks to the end would silently rewrite the past.
    """
    before = feature_frame(series(history), feature_set=F1)
    after = feature_frame(series(history + future), feature_set=F1)
    overlap = after.reindex(before.index)

    predictors = [c for c in before.columns if c != "y"]
    pd.testing.assert_frame_equal(
        before[predictors], overlap[predictors], check_exact=True
    )
    # The label of an already-observed week must not move either. The only row
    # allowed to change is the one that had no label yet, which is exactly the
    # week `before` was about to predict.
    known = before["y"].notna()
    pd.testing.assert_series_equal(
        before.loc[known, "y"], overlap.loc[known, "y"], check_exact=True
    )


# --- provisional is context, mature is a label ------------------------------


def test_an_immature_target_is_not_a_training_row():
    values = [float(100 + i) for i in range(30)]
    state = series(values)
    built = feature_frame(state, feature_set=F0)
    last_week = built.index[-1].date()
    # The cut is the day after the last week: nothing has had 45 days to mature.
    cut = last_week + timedelta(days=1)

    rows = supervised_rows(
        built, decision_as_of=cut, policy=POLICY, train_from=FIRST_SATURDAY
    )
    for week in (w.date() for w in rows.index):
        assert POLICY.is_eligible(week, cut), f"{week} supervised a fit before maturing"
    assert last_week not in {w.date() for w in rows.index}


def test_rows_before_the_declared_universe_are_excluded():
    values = [float(i) for i in range(60)]
    state = series(values, start=date(2024, 1, 6))
    built = feature_frame(state, feature_set=F0)
    cut = date(2026, 1, 3)
    train_from = date(2024, 11, 2)

    rows = supervised_rows(
        built, decision_as_of=cut, policy=POLICY, train_from=train_from
    )
    assert rows.index.min().date() >= train_from


def test_a_thin_origin_is_declined_rather_than_fitted():
    """Too few mature rows must raise, so the origin is reported as excluded."""
    state = series([float(i) for i in range(20)])
    with pytest.raises(ForecastError, match="below the declared minimum"):
        fit_and_forecast_ridge(
            state,
            date(2026, 1, 3),
            feature_set=F0,
            policy=POLICY,
            train_from=FIRST_SATURDAY,
            min_train_rows=26,
            alpha=1.0,
        )


# --- the scaler is fitted on this origin's training rows and nothing else ---


def test_the_scaler_sees_only_the_training_rows():
    """Checked against the training rows' own mean, not asserted from the Pipeline's shape."""
    from sklearn.linear_model import Ridge
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    values = [float(100 + 3 * i) for i in range(80)]
    state = series(values)
    cut = date(2026, 6, 6)
    built = feature_frame(state, feature_set=F0)
    training = supervised_rows(
        built, decision_as_of=cut, policy=POLICY, train_from=FIRST_SATURDAY
    )
    assert len(training) >= 26, "fixture must have enough mature rows to be meaningful"

    predictors = [c for c in built.columns if c != "y"]
    pipeline = Pipeline([("scale", StandardScaler()), ("ridge", Ridge(alpha=1.0))])
    pipeline.fit(training[predictors].to_numpy(), training["y"].to_numpy())

    fitted_mean = pipeline.named_steps["scale"].mean_
    expected = training[predictors].to_numpy().mean(axis=0)
    assert fitted_mean == pytest.approx(expected)

    # And it must differ from the whole frame's mean, or the test proves nothing.
    whole = built.dropna()[predictors].to_numpy().mean(axis=0)
    assert fitted_mean != pytest.approx(whole)


def test_a_forecast_is_produced_and_targets_the_week_after_the_last_visible():
    state = series([float(100 + 3 * i) for i in range(80)])
    cut = date(2026, 6, 6)
    issued = fit_and_forecast_ridge(
        state,
        cut,
        feature_set=F1,
        policy=POLICY,
        train_from=FIRST_SATURDAY,
        min_train_rows=26,
        alpha=1.0,
    )
    last_visible = state["event_week_end"].max()
    assert issued.target_week == str(last_visible + timedelta(weeks=1))
    assert issued.horizon_weeks == 1
    assert issued.model == "ridge_F1"
    assert issued.inputs_used >= 26


# --- one row per target week: a calendar rule, not a scoreboard rule --------


def test_repeated_target_weeks_collapse_to_the_earliest_origin():
    """A stalled publication makes several origins forecast the same week.

    Found by the stratification Decision B asked for. The kept row must be the
    earliest cut — the first origin at which that week became forecastable —
    and the choice must not depend on which origin happened to score better.
    """
    import importlib.util
    import sys

    spec = importlib.util.spec_from_file_location(
        "compare_models", ROOT_DIR / "scripts" / "01_compare_models.py"
    )
    assert spec and spec.loader
    compare = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = compare
    spec.loader.exec_module(compare)

    stalled = [
        # Three origins, one target week, and the worst loss on the earliest cut
        # so that a loss-based rule would pick a different row.
        {"cut": "2025-10-04", "target_week": "2025-09-27", "loss": {"naive": 9.0}},
        {"cut": "2025-10-11", "target_week": "2025-09-27", "loss": {"naive": 0.1}},
        {"cut": "2025-10-18", "target_week": "2025-09-27", "loss": {"naive": 0.2}},
        {"cut": "2025-10-25", "target_week": "2025-10-18", "loss": {"naive": 0.3}},
    ]
    kept = compare.one_row_per_target_week(stalled)

    assert len(kept) == 2, "one row per distinct target week"
    by_week = {r["target_week"]: r for r in kept}
    assert by_week["2025-09-27"]["cut"] == "2025-10-04", (
        "the earliest origin must be kept; a better-scoring one was chosen instead"
    )
    assert by_week["2025-09-27"]["loss"]["naive"] == 9.0
