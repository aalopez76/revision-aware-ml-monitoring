"""The gate's arithmetic: the denominator, the interval, and what opens G3.

N1 is the one figure the project exists to produce, so the ways it could be
quietly wrong each get a test:

* the denominator must not depend on what the arms decided -- a cut where every
  arm abstains still counts, or the information being measured would select its
  own denominator;
* the interval must be Wilson and not a normal approximation, because a
  discordance can sit at 0 or 1 and those are exactly the two outcomes the gate
  has to report honestly;
* the gate must read the **lower** bound, so a large estimate on thin support
  does not open G3;
* a forecast must not be scored at the cut that issued it, and an immature label
  must not be scored at all.

The two deduplication rules -- P2's and G2's -- are separate functions in
separate scripts, which is a duplication the plan's removal of `evaluation.py`
left in place. The last test asserts they agree, so divergence fails here
instead of silently changing a denominator.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path

import pytest

from revmon.forecasting import LossScale
from revmon.temporal import MaturityPolicy

ROOT_DIR = Path(__file__).resolve().parents[1]
POLICY = MaturityPolicy(days=45, declared_in="tests")
SCALE = LossScale(s_dev=100.0, window_from="2024-11-19", window_to="2025-06-30", pairs=24)


def load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, ROOT_DIR / "scripts" / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


g2 = load("discordance", "02_discordance.py")


# --- the interval -----------------------------------------------------------


def test_wilson_matches_the_published_interval():
    """The figure the artefact carries, recomputed from the definition."""
    low, high = g2.wilson(25, 55)
    assert (low, high) == (0.330253, 0.584773)


def test_wilson_stays_inside_zero_and_one_at_the_extremes():
    """Where a normal approximation goes outside the unit interval and lies."""
    assert g2.wilson(0, 20)[0] == 0.0
    assert g2.wilson(20, 20)[1] == 1.0
    # And it is not degenerate: a zero count still carries uncertainty upwards.
    assert g2.wilson(0, 20)[1] > 0.0


def test_wilson_is_undefined_on_no_support_rather_than_zero():
    assert g2.wilson(0, 0) is None


# --- the denominator is exogenous ------------------------------------------


def test_a_cut_where_every_arm_abstains_still_counts_in_the_denominator():
    """Conditioning on the arms emitting a 'normal' decision is post-treatment."""
    decisions = [
        {"d_00": "ABSTENERSE", "d_11": "ABSTENERSE"},
        {"d_00": "CONTINUAR", "d_11": "INVESTIGAR_DATO"},
    ]
    result = g2.discordance(decisions, "d_11", "d_00")
    assert result["denominator"] == 2, "the abstention was dropped from the denominator"
    assert result["numerator"] == 1
    assert result["estimate"] == 0.5


def test_an_abstention_on_one_side_only_is_a_discordance():
    decisions = [{"d_00": "CONTINUAR", "d_11": "ABSTENERSE"}]
    assert g2.discordance(decisions, "d_11", "d_00")["numerator"] == 1


def test_identical_recommendations_are_not_discordant_however_unusual():
    decisions = [{"d_00": "EVALUAR_REENTRENO", "d_11": "EVALUAR_REENTRENO"}] * 5
    assert g2.discordance(decisions, "d_11", "d_00")["estimate"] == 0.0


def test_the_contingency_shows_which_recommendation_became_which():
    decisions = [
        {"d_00": "CONTINUAR", "d_11": "INVESTIGAR_DATO"},
        {"d_00": "CONTINUAR", "d_11": "INVESTIGAR_DATO"},
        {"d_00": "CONTINUAR", "d_11": "CONTINUAR"},
    ]
    table = g2.contingency(decisions, "d_11", "d_00")
    assert table["d_00=CONTINUAR"] == {"d_11=INVESTIGAR_DATO": 2, "d_11=CONTINUAR": 1}


# --- the gate ---------------------------------------------------------------


def test_the_gate_reads_the_lower_bound_not_the_estimate():
    """A large discordance on thin support must not open G3."""
    thin = {"estimate": 0.8, "numerator": 4, "denominator": 5, "wilson_95": g2.wilson(4, 5)}
    assert thin["wilson_95"][0] > 0.10, "fixture must have a high lower bound to be fair"
    assert g2.authorizes_g3(thin, 5, min_support=20) is False, "support was ignored"


def test_the_gate_closes_when_the_bound_sits_below_the_floor():
    few = {"wilson_95": g2.wilson(3, 55)}
    assert few["wilson_95"][0] < 0.10
    assert g2.authorizes_g3(few, 55, min_support=20) is False


def test_the_gate_opens_on_the_measured_result():
    measured = {"wilson_95": g2.wilson(25, 55)}
    assert g2.authorizes_g3(measured, 55, min_support=20) is True


def test_a_missing_interval_never_opens_the_gate():
    assert g2.authorizes_g3({"wilson_95": None}, 55, min_support=20) is False


# --- no forecast is scored against its own cut -----------------------------


def test_a_forecast_issued_at_the_cut_is_not_scored_at_it():
    """Scoring a forecast at its own origin is scoring hindsight."""
    rows = [
        {"cut": "2025-07-05", "target_week": "2025-07-05", "y_pred": 100.0},
        {"cut": "2025-10-04", "target_week": "2025-10-04", "y_pred": 100.0},
    ]
    labels = {date(2025, 7, 5): 200.0, date(2025, 10, 4): 200.0}
    loss, scored = g2.score_at(date(2025, 10, 4), rows, labels, SCALE, POLICY)
    assert scored == 1, "the forecast issued at this cut was scored at it"
    assert loss == pytest.approx(1.0)


def test_an_immature_label_is_not_scored():
    rows = [{"cut": "2025-07-05", "target_week": "2025-07-05", "y_pred": 100.0}]
    labels = {date(2025, 7, 5): 200.0}
    # Only 14 days after the target week: nothing has had 45 days to mature.
    loss, scored = g2.score_at(date(2025, 7, 19), rows, labels, SCALE, POLICY)
    assert (loss, scored) == (None, 0)


def test_a_week_with_no_mature_label_at_all_is_not_invented():
    rows = [{"cut": "2025-07-05", "target_week": "2025-07-05", "y_pred": 100.0}]
    loss, scored = g2.score_at(date(2026, 1, 3), rows, {}, SCALE, POLICY)
    assert (loss, scored) == (None, 0)


# --- the two deduplication rules must not drift apart ----------------------


def test_both_scripts_collapse_repeated_target_weeks_identically():
    """A duplicated rule that decides a denominator, pinned to one behaviour."""
    p2 = load("compare_models", "01_compare_models.py")
    stalled = [
        {"cut": "2025-10-04", "target_week": "2025-09-27", "loss": {"naive": 9.0}},
        {"cut": "2025-10-11", "target_week": "2025-09-27", "loss": {"naive": 0.1}},
        {"cut": "2025-10-25", "target_week": "2025-10-18", "loss": {"naive": 0.3}},
    ]
    assert g2.one_row_per_target_week(stalled) == p2.one_row_per_target_week(stalled)
    kept = g2.one_row_per_target_week(stalled)
    assert [r["cut"] for r in kept] == ["2025-10-04", "2025-10-25"]


def test_the_spread_reports_missing_values_rather_than_hiding_them():
    assert g2._spread([None, None]) == {"n": 2, "n_missing": 2}
    spread = g2._spread([1.0, None, 3.0, 5.0])
    assert spread["n_missing"] == 1 and spread["median"] == 3.0 and spread["max"] == 5.0


def test_the_config_the_gate_reads_is_the_one_on_disk():
    """A gate governed by a file that is not versioned is not governed."""
    assert g2.CONFIG.exists()
    assert g2.CONFIG.relative_to(ROOT_DIR) == Path("config") / "g2_signals.json"
    config = g2.load_config()
    assert config["signals"]["R"]["statistic"] == "mean_abs_relative_revision"
    assert config["n1"]["min_support_distinct_weeks"] == 20
    assert "0.10" in config["g3_gate"]["authorizes_g3_if"]
