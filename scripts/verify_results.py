"""Check that the numerical claims in the README match the artefacts.

This asks a different question from the test suite. `pytest` asks whether the
software works; this asks whether the **published claims still correspond to the
files that back them**. Code can be correct while a document quietly drifts away
from it.

Each claim names where it appears, how to find it in `reports/results/`, and the
tolerance it is allowed. Tolerances are tight enough to catch a changed analysis
and loose enough to survive the last reported digit.

**This script and the README are updated in the same commit.** A number that
changes on purpose changes here too; one that changes by accident fails here
first. A figure that appears in the README without a row here is a defect, not
an exception.

It reads only versioned JSON, so it needs no data download and no recomputation,
which is why CI can run it.

Exit code is non-zero when any claim fails.
"""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "reports" / "results"


@dataclass(frozen=True)
class Claim:
    """One number the README states, and where it comes from."""

    label: str
    source: str                      # file in reports/results/
    path: tuple[str | int, ...]      # keys to walk; ints index into lists
    expected: float
    tolerance: float
    scale: float = 1.0               # multiply the stored value before comparing

    def read(self) -> float:
        payload: Any = json.loads((RESULTS / self.source).read_text(encoding="utf-8"))
        for key in self.path:
            payload = payload[key]
        return float(payload) * self.scale


@dataclass(frozen=True)
class ExactClaim:
    """One non-numeric figure the README states: a date, a window, a verdict.

    Added because the rule is that **every** figure needs a row, and a date is a
    figure. A verifier that only tracked floats would have left the measured
    source windows — the most load-bearing numbers G0 produced — untraceable by
    construction, and that gap would read as compliance.
    """

    label: str
    source: str
    path: tuple[str | int, ...]
    expected: str

    def read(self) -> str:
        payload: Any = json.loads((RESULTS / self.source).read_text(encoding="utf-8"))
        for key in self.path:
            payload = payload[key]
        return str(payload)


# ---------------------------------------------------------------------------
# One row per figure the documents state, added in the same commit that puts the
# figure in the document. G0's measured source windows are here; G1 adds the
# first real run, G2 the discordance N1 with its numerator, denominator and
# abstentions, and G3 — only if the gate opens — the cost frontier.
#
# This script checks correspondence between a published number and the artefact
# behind it. It does **not** check that the computation is right, and it cannot
# tell an E1 measurement from an E3 proposal — that needs judgement, which is
# why it lives in /auditar-cifras and not here.
#
# Some of these grow: the publication calendar gains entries every few days, and
# the version history gains a week every week. That is not a flaw in the rows —
# it is the rule working. A figure that changes on purpose changes here and in
# the document together, which is why the documents date the run they quote.
# ---------------------------------------------------------------------------

G0 = "00_source_feasibility.json"
G1 = "01_vertical_slice.json"
G1A = "01_modeling_support.json"
P2 = "01_model_comparison.json"
G2A = "02_signal_diagnostics.json"
G2 = "02_discordance.json"

CLAIMS: list[Claim] = [
    Claim(
        label="event history, weeks",
        source=G0,
        path=("g0_6_support", "event_history_weeks"),
        expected=322,
        tolerance=0,
    ),
    Claim(
        label="version history, weeks",
        source=G0,
        path=("g0_6_support", "version_history_weeks"),
        expected=99,
        tolerance=0,
    ),
    Claim(
        label="event weeks with no version history",
        source=G0,
        path=("g0_6_support", "event_weeks_without_version_history"),
        expected=223,
        tolerance=0,
    ),
    Claim(
        label="ceiling: weekly national cuts",
        source=G0,
        path=("g0_6_support", "max_weekly_national_cuts"),
        expected=99,
        tolerance=0,
    ),
    Claim(
        label="publication dates in the calendar",
        source=G0,
        path=("g0_4_calendar", "publication_dates"),
        expected=189,
        tolerance=0,
    ),
    Claim(
        label="publications per ISO week, median",
        source=G0,
        path=("g0_4_calendar", "publications_per_iso_week", "median"),
        expected=2.0,
        tolerance=0,
    ),
    Claim(
        label="signals offered by the source",
        source=G0,
        path=("g0_1_2_metadata", "signals_total"),
        expected=319,
        tolerance=0,
    ),
    Claim(
        label="archive: publications in window",
        source=G0,
        path=("g0_3_archive_semantics", "calendar_publications_in_window"),
        expected=102,
        tolerance=0,
    ),
    Claim(
        label="archive: share of publications present",
        source=G0,
        path=("g0_3_archive_semantics", "share_of_publications_present"),
        expected=0.98,
        tolerance=0.005,
    ),
    Claim(
        label="archive: versions per key, median",
        source=G0,
        path=("g0_3_archive_semantics", "rows_per_key", "median"),
        expected=17.0,
        tolerance=0,
    ),
    Claim(
        label="archive: versions per key, min",
        source=G0,
        path=("g0_3_archive_semantics", "rows_per_key", "min"),
        expected=2,
        tolerance=0,
    ),
    Claim(
        label="hub cross-check: overlapping weeks",
        source=G0,
        path=("g0_5_hub_alignment", "overlapping_weeks"),
        expected=245,
        tolerance=0,
    ),
    Claim(
        label="hub cross-check: disagreeing weeks",
        source=G0,
        path=("g0_5_hub_alignment", "disagreeing_weeks"),
        expected=0,
        tolerance=0,
    ),
    Claim(
        label="G0 requests issued",
        source=G0,
        path=("run", "budget", "requests_issued"),
        expected=13,
        tolerance=0,
    ),
    # G1-A support. These are the figures that replace an earlier review's
    # unmeasured guess of "40-60 folds"; the real count is nearly double, which
    # is exactly why the guess was never allowed into a document.
    Claim(
        label="candidate scheduled cuts",
        source=G1A,
        path=("temporally_eligible_origins", "candidate_scheduled_cuts"),
        expected=100,
        tolerance=0,
    ),
    Claim(
        label="eligible origins, declared 45-day policy",
        source=G1A,
        path=("temporally_eligible_origins", "declared_policy_origins"),
        expected=93,
        tolerance=0,
    ),
    Claim(
        label="eligible origins, 90-day sensitivity",
        source=G1A,
        path=("temporally_eligible_origins", "by_maturity_days", "90", "origins"),
        expected=87,
        tolerance=0,
    ),
    Claim(
        label="publication lag, max days",
        source=G1A,
        path=("publication_lag_days", "max"),
        expected=49,
        tolerance=0,
    ),
    Claim(
        label="publication lag, median days",
        source=G1A,
        path=("publication_lag_days", "median"),
        expected=7,
        tolerance=0,
    ),
    # Zero by construction at horizon +1. If this ever stops being zero, the
    # word "nowcast" in the README is wrong and this row says so.
    Claim(
        label="pre-week forecasts on disk",
        source=G1,
        path=("emission_audit", "pre_week_forecasts"),
        expected=0,
        tolerance=0,
    ),
    Claim(
        label="predictions with unverifiable emission",
        source=G1,
        path=("emission_audit", "not_verifiable"),
        expected=0,
        tolerance=0,
    ),
    # P2 comparison. The support rows are structural and carry tolerance 0; the
    # losses move as weeks arrive, so they carry the run's date in the artefact
    # and a tolerance at the last reported digit.
    Claim(
        label="P2 common origins",
        source=P2,
        path=("support", "common_origins"),
        expected=61,
        tolerance=0,
    ),
    Claim(
        label="P2 distinct target weeks",
        source=P2,
        path=("support", "distinct_target_weeks"),
        expected=55,
        tolerance=0,
    ),
    Claim(
        label="P2 origins above distinct weeks",
        source=P2,
        path=("support", "origins_above_distinct_weeks"),
        expected=6,
        tolerance=0,
    ),
    Claim(
        label="M0 scaled loss, 55 weeks",
        source=P2,
        path=("on_distinct_target_weeks", "naive", "mean_scaled_loss"),
        expected=0.314624,
        tolerance=5e-6,
    ),
    Claim(
        label="ridge_F0 scaled loss, 55 weeks",
        source=P2,
        path=("on_distinct_target_weeks", "ridge_F0", "mean_scaled_loss"),
        expected=0.60293,
        tolerance=5e-6,
    ),
    Claim(
        label="ridge_F1 scaled loss, 55 weeks",
        source=P2,
        path=("on_distinct_target_weeks", "ridge_F1", "mean_scaled_loss"),
        expected=0.378141,
        tolerance=5e-6,
    ),
    Claim(
        label="ridge_F1 weeks beating M0",
        source=P2,
        path=("paired_against_m0", "ridge_F1", "beats_m0"),
        expected=8,
        tolerance=0,
    ),
    Claim(
        label="ridge_F1 weeks losing to M0",
        source=P2,
        path=("paired_against_m0", "ridge_F1", "loses_to_m0"),
        expected=47,
        tolerance=0,
    ),
    # The degenerate stratum, tracked so it cannot quietly be read as n=6.
    Claim(
        label="delayed-publication stratum: distinct weeks",
        source=P2,
        path=("by_publication_lag", "delayed_publication", "distinct_target_weeks"),
        expected=1,
        tolerance=0,
    ),
    # --- G2-A: the signals, before any threshold was declared ---------------
    #
    # The saturation rows are the load-bearing ones. If `revised_share` ever
    # stops being 1.0, the conclusion that the share cannot discriminate stops
    # holding, and these rows are what makes that visible instead of silent.
    Claim(
        label="G2-A development cuts",
        source=G2A,
        path=("window", "development_cuts"),
        expected=32,
        tolerance=0,
    ),
    Claim(
        label="comparable pairs in development",
        source=G2A,
        path=("revision_by_publication_lag", "all_comparable_pairs", "pairs"),
        expected=1046,
        tolerance=0,
    ),
    Claim(
        label="revised pairs in development",
        source=G2A,
        path=("revision_by_publication_lag", "all_comparable_pairs", "revised"),
        expected=1046,
        tolerance=0,
    ),
    Claim(
        label="revised share, all pairs",
        source=G2A,
        path=("revision_by_publication_lag", "all_comparable_pairs", "revised_share"),
        expected=1.0,
        tolerance=0,
    ),
    Claim(
        label="R as a share: distinct values, edge",
        source=G2A,
        path=("signals", "r_series_edge", "distribution", "distinct_values"),
        expected=1,
        tolerance=0,
    ),
    Claim(
        label="R as a share: distinct values, anchored",
        source=G2A,
        path=("signals", "r_matured_window", "distribution", "distinct_values"),
        expected=1,
        tolerance=0,
    ),
    # The decay profile: three points of it, which is what says the structural
    # restatement window is about three weeks rather than the eight G1 used.
    Claim(
        label="median |revision|, 0-7 day lag",
        source=G2A,
        path=("revision_by_publication_lag", "by_lag_days", "0-7",
              "abs_relative_revision", "median"),
        expected=0.037626,
        tolerance=1e-6,
    ),
    Claim(
        label="median |revision|, 22-28 day lag",
        source=G2A,
        path=("revision_by_publication_lag", "by_lag_days", "22-28",
              "abs_relative_revision", "median"),
        expected=0.001647,
        tolerance=1e-6,
    ),
    Claim(
        label="median |revision|, >180 day lag",
        source=G2A,
        path=("revision_by_publication_lag", "by_lag_days", ">180",
              "abs_relative_revision", "median"),
        expected=0.000625,
        tolerance=1e-6,
    ),
    Claim(
        label="median |revision|, 8-14 day lag",
        source=G2A,
        path=("revision_by_publication_lag", "by_lag_days", "8-14",
              "abs_relative_revision", "median"),
        expected=0.012175,
        tolerance=1e-6,
    ),
    Claim(
        label="median |revision|, 91-180 day lag",
        source=G2A,
        path=("revision_by_publication_lag", "by_lag_days", "91-180",
              "abs_relative_revision", "median"),
        expected=0.000326,
        tolerance=1e-6,
    ),
    # The pair counts behind each bucket. The saturation claim is only as strong
    # as the n it holds on, so the n is tracked beside the share.
    Claim(
        label="pairs, 0-7 day lag",
        source=G2A,
        path=("revision_by_publication_lag", "by_lag_days", "0-7", "pairs"),
        expected=33,
        tolerance=0,
    ),
    Claim(
        label="pairs, 8-14 day lag",
        source=G2A,
        path=("revision_by_publication_lag", "by_lag_days", "8-14", "pairs"),
        expected=62,
        tolerance=0,
    ),
    Claim(
        label="pairs, 22-28 day lag",
        source=G2A,
        path=("revision_by_publication_lag", "by_lag_days", "22-28", "pairs"),
        expected=53,
        tolerance=0,
    ),
    Claim(
        label="pairs, 91-180 day lag",
        source=G2A,
        path=("revision_by_publication_lag", "by_lag_days", "91-180", "pairs"),
        expected=167,
        tolerance=0,
    ),
    Claim(
        label="pairs, >180 day lag",
        source=G2A,
        path=("revision_by_publication_lag", "by_lag_days", ">180", "pairs"),
        expected=359,
        tolerance=0,
    ),
    Claim(
        label="R as magnitude: median",
        source=G2A,
        path=("signals", "r_magnitude_mean", "distribution", "median"),
        expected=0.010218,
        tolerance=1e-6,
    ),
    Claim(
        label="R as magnitude: distinct values",
        source=G2A,
        path=("signals", "r_magnitude_mean", "distribution", "distinct_values"),
        expected=31,
        tolerance=0,
    ),
    # C against its own declared alarm of 2.0 points: the observed ceiling is
    # the figure that says the threshold was never reachable.
    Claim(
        label="C at the edge: observed maximum",
        source=G2A,
        path=("signals", "c_series_edge", "distribution", "max"),
        expected=0.1187,
        tolerance=1e-6,
    ),
    Claim(
        label="C anchored: observed maximum",
        source=G2A,
        path=("signals", "c_matured_window", "distribution", "max"),
        expected=0.033225,
        tolerance=1e-6,
    ),
    Claim(
        label="cuts reaching PERFORMANCE at 4 labels",
        source=G2A,
        path=("performance_branch_reachability", "by_min_mature_labels", "4",
              "cuts_reaching_performance"),
        expected=22,
        tolerance=0,
    ),
    # --- G2: the gate -------------------------------------------------------
    #
    # N1 with its numerator, denominator and interval, the four simple effects
    # and the two contrasts. The zeros are tracked as tightly as the rest: that
    # the revision factor changed nothing is the result, so it has to be as hard
    # to lose from the document as a positive number would be.
    Claim(
        label="N1 = D(11,00)",
        source=G2,
        path=("primary_cell", "n1_d11_vs_d00", "estimate"),
        expected=0.454545,
        tolerance=1e-6,
    ),
    Claim(
        label="N1 numerator",
        source=G2,
        path=("primary_cell", "n1_d11_vs_d00", "numerator"),
        expected=25,
        tolerance=0,
    ),
    Claim(
        label="N1 denominator: distinct target weeks",
        source=G2,
        path=("primary_cell", "n1_d11_vs_d00", "denominator"),
        expected=55,
        tolerance=0,
    ),
    Claim(
        label="N1 Wilson lower bound",
        source=G2,
        path=("primary_cell", "n1_d11_vs_d00", "wilson_95", 0),
        expected=0.330253,
        tolerance=1e-6,
    ),
    Claim(
        label="N1 Wilson upper bound",
        source=G2,
        path=("primary_cell", "n1_d11_vs_d00", "wilson_95", 1),
        expected=0.584773,
        tolerance=1e-6,
    ),
    Claim(
        label="simple effect: revisions alone",
        source=G2,
        path=("primary_cell", "simple_effects", "d10_vs_d00", "estimate"),
        expected=0.0,
        tolerance=0,
    ),
    Claim(
        label="simple effect: coverage alone",
        source=G2,
        path=("primary_cell", "simple_effects", "d01_vs_d00", "estimate"),
        expected=0.454545,
        tolerance=1e-6,
    ),
    Claim(
        label="simple effect: coverage given revisions",
        source=G2,
        path=("primary_cell", "simple_effects", "d11_vs_d10", "estimate"),
        expected=0.454545,
        tolerance=1e-6,
    ),
    Claim(
        label="simple effect: revisions given coverage",
        source=G2,
        path=("primary_cell", "simple_effects", "d11_vs_d01", "estimate"),
        expected=0.0,
        tolerance=0,
    ),
    Claim(
        label="interaction contrast: coverage",
        source=G2,
        path=("primary_cell", "interaction_contrasts",
              "coverage_given_revisions_minus_coverage_alone"),
        expected=0.0,
        tolerance=0,
    ),
    Claim(
        label="interaction contrast: revisions",
        source=G2,
        path=("primary_cell", "interaction_contrasts",
              "revisions_given_coverage_minus_revisions_alone"),
        expected=0.0,
        tolerance=0,
    ),
    # The grid, so the headline cannot be quoted without its dependence.
    Claim(
        label="N1 over the grid: minimum",
        source=G2,
        path=("threshold_sensitivity", "n1_min"),
        expected=0.454545,
        tolerance=1e-6,
    ),
    Claim(
        label="N1 over the grid: maximum",
        source=G2,
        path=("threshold_sensitivity", "n1_max"),
        expected=0.818182,
        tolerance=1e-6,
    ),
    # The two signals' evaluation range, which is what makes the alarms readable.
    Claim(
        label="R magnitude in evaluation: maximum",
        source=G2,
        path=("signal_values_in_evaluation", "revision_magnitude", "max"),
        expected=0.016014,
        tolerance=1e-6,
    ),
    Claim(
        label="C drop in evaluation: maximum",
        source=G2,
        path=("signal_values_in_evaluation", "coverage_drop", "max"),
        expected=2.82,
        tolerance=1e-6,
    ),
    Claim(
        label="eligible origins before deduplication",
        source=G2,
        path=("support", "eligible_origins"),
        expected=61,
        tolerance=0,
    ),
    Claim(
        label="weeks collapsed by the calendar rule",
        source=G2,
        path=("support", "collapsed_by_calendar"),
        expected=6,
        tolerance=0,
    ),
    Claim(
        label="candidate cuts measured",
        source=G2,
        path=("support", "candidate_cuts"),
        expected=68,
        tolerance=0,
    ),
    # The thresholds themselves are figures the README states, so the artefact
    # that was computed under them is what backs them -- not the config file,
    # which declares them. A run under a different alarm fails here.
    Claim(
        label="declared revision alarm",
        source=G2,
        path=("primary_cell", "thresholds", "revision_alarm"),
        expected=0.02,
        tolerance=1e-9,
    ),
    Claim(
        label="declared coverage alarm",
        source=G2,
        path=("primary_cell", "thresholds", "coverage_drop_alarm"),
        expected=0.02,
        tolerance=1e-9,
    ),
    Claim(
        label="R magnitude in evaluation: minimum",
        source=G2,
        path=("signal_values_in_evaluation", "revision_magnitude", "min"),
        expected=0.006009,
        tolerance=1e-6,
    ),
    # The grid cells where the revision factor is NOT inert. These rows exist
    # because the primary cell alone would let the README imply that revision
    # information does not move recommendations in this series, which the other
    # two declared alarms contradict. The qualification has to be as hard to
    # lose from the document as the headline is.
    Claim(
        label="revisions alone at alarm 0.005",
        source=G2,
        path=("by_threshold_cell", "R=0.005,C=0.02", "simple_effects",
              "d10_vs_d00", "estimate"),
        expected=0.818182,
        tolerance=1e-6,
    ),
    Claim(
        label="revisions alone at alarm 0.005: numerator",
        source=G2,
        path=("by_threshold_cell", "R=0.005,C=0.02", "simple_effects",
              "d10_vs_d00", "numerator"),
        expected=45,
        tolerance=0,
    ),
    Claim(
        label="revisions alone at alarm 0.01",
        source=G2,
        path=("by_threshold_cell", "R=0.01,C=0.02", "simple_effects",
              "d10_vs_d00", "estimate"),
        expected=0.254545,
        tolerance=1e-6,
    ),
    Claim(
        label="revisions alone at alarm 0.01: numerator",
        source=G2,
        path=("by_threshold_cell", "R=0.01,C=0.02", "simple_effects",
              "d10_vs_d00", "numerator"),
        expected=14,
        tolerance=0,
    ),
    Claim(
        label="N1 at alarm 0.01",
        source=G2,
        path=("by_threshold_cell", "R=0.01,C=0.02", "n1_d11_vs_d00", "estimate"),
        expected=0.581818,
        tolerance=1e-6,
    ),
    Claim(
        label="N1 at alarm 0.005",
        source=G2,
        path=("by_threshold_cell", "R=0.005,C=0.02", "n1_d11_vs_d00", "estimate"),
        expected=0.818182,
        tolerance=1e-6,
    ),
    # The upper bound on the zeros. "Revisions changed nothing" is a statement
    # about what was observed; this is the figure that says what the 55 weeks
    # actually rule out, and without it the zero reads as an exact null.
    Claim(
        label="revisions alone: Wilson upper bound",
        source=G2,
        path=("primary_cell", "simple_effects", "d10_vs_d00", "wilson_95", 1),
        expected=0.065285,
        tolerance=1e-6,
    ),
    Claim(
        label="revisions given coverage: Wilson upper bound",
        source=G2,
        path=("primary_cell", "simple_effects", "d11_vs_d01", "wilson_95", 1),
        expected=0.065285,
        tolerance=1e-6,
    ),
    # What each arm recommended. The abstentions are tracked although they are
    # zero: the rule is that ABSTENERSE is a category and is reported even when
    # empty, and a row that only exists when the number is interesting is not a
    # verifier.
    Claim(
        label="abstentions, base arm",
        source=G2,
        path=("primary_cell", "abstentions", "d_00"),
        expected=0,
        tolerance=0,
    ),
    Claim(
        label="abstentions, both-information arm",
        source=G2,
        path=("primary_cell", "abstentions", "d_11"),
        expected=0,
        tolerance=0,
    ),
    Claim(
        label="d_00 recommends CONTINUAR",
        source=G2,
        path=("primary_cell", "action_counts", "d_00", "CONTINUAR"),
        expected=45,
        tolerance=0,
    ),
    Claim(
        label="d_00 recommends ESPERAR_MADUREZ",
        source=G2,
        path=("primary_cell", "action_counts", "d_00", "ESPERAR_MADUREZ"),
        expected=10,
        tolerance=0,
    ),
    Claim(
        label="d_11 recommends CONTINUAR",
        source=G2,
        path=("primary_cell", "action_counts", "d_11", "CONTINUAR"),
        expected=20,
        tolerance=0,
    ),
    Claim(
        label="d_11 recommends INVESTIGAR_DATO",
        source=G2,
        path=("primary_cell", "action_counts", "d_11", "INVESTIGAR_DATO"),
        expected=25,
        tolerance=0,
    ),
    # --- figures the earlier gates state and the README now cites ------------
    Claim(
        label="s_dev, calibration scale",
        source=P2,
        path=("loss_scale", "s_dev"),
        expected=4967.25,
        tolerance=1e-6,
    ),
    Claim(
        label="calibration pairs behind s_dev",
        source=P2,
        path=("loss_scale", "pairs"),
        expected=24,
        tolerance=0,
    ),
    Claim(
        label="days between publications, median",
        source=G0,
        path=("g0_4_calendar", "days_between_publications", "median"),
        expected=2.5,
        tolerance=1e-9,
    ),
    Claim(
        label="observed run: coverage drop",
        source=G1,
        path=("observed_run", "recommendation", "evidence", "coverage_drop"),
        expected=4.5875,
        tolerance=1e-6,
    ),
    Claim(
        label="observed run: matured labels behind the loss",
        source=G1,
        path=("observed_run", "recommendation", "evidence", "mature_labels"),
        expected=28,
        tolerance=0,
    ),
]

EXACT_CLAIMS: list[ExactClaim] = [
    # The gate's verdict as a figure, because a verdict is a figure.
    ExactClaim(
        label="G2 gate authorizes G3",
        source=G2,
        path=("g3_gate", "authorizes_g3"),
        expected="True",
    ),
    ExactClaim(
        label="G2 evidence class",
        source=G2,
        path=("manifest", "config", "evidence_class"),
        expected="E2 controlled replay: forecasts reconstructed, not issued",
    ),
    ExactClaim(
        label="first recoverable report_time",
        source=G0,
        path=("g0_1_2_metadata", "report_time_range", "first"),
        expected="2024-11-19T00:00:00Z",
    ),
    ExactClaim(
        label="first reference_time",
        source=G0,
        path=("g0_1_2_metadata", "reference_time_range", "first"),
        expected="2020-08-08",
    ),
    ExactClaim(
        label="archive semantics verdict",
        source=G0,
        path=("g0_3_archive_semantics", "semantics_verdict"),
        expected="multiple_versions_per_key",
    ),
    ExactClaim(
        label="G0 verdict",
        source=G0,
        path=("verdict", "verdict"),
        expected="PROCEED",
    ),
    # The claim the project now makes about what it emits. If a future run ever
    # produced a pre-week forecast this row would fail, which is the point: the
    # word "nowcast" in the README would then be wrong.
    ExactClaim(
        label="observed run emission class",
        source=G1,
        path=("observed_run", "emission_class"),
        expected="intra_week_nowcast",
    ),
    ExactClaim(
        label="observed run recommendation",
        source=G1,
        path=("observed_run", "recommendation", "action"),
        expected="INVESTIGAR_DATO",
    ),
    # The whole distribution of actions, not only the counts that are non-zero.
    # A numeric row cannot state that an action was never emitted, because the
    # artefact omits the key entirely; these two rows are what back the README
    # saying EVALUAR_REENTRENO and ABSTENERSE never appear.
    ExactClaim(
        label="d_00 action distribution, in full",
        source=G2,
        path=("primary_cell", "action_counts", "d_00"),
        expected="{'CONTINUAR': 45, 'ESPERAR_MADUREZ': 10}",
    ),
    ExactClaim(
        label="d_11 action distribution, in full",
        source=G2,
        path=("primary_cell", "action_counts", "d_11"),
        expected="{'CONTINUAR': 20, 'ESPERAR_MADUREZ': 10, 'INVESTIGAR_DATO': 25}",
    ),
]

# --- claims about the manifest, checked per schema version ------------------
#
# Separate from the rows above because the question is different: not "does the
# published figure still match the artefact", but "does this run name the
# documents that governed it". And it is version-aware on purpose. A run written
# last week must not be required to match a document edited after it, or every
# past result would turn red the moment a typo is fixed. Older schemas are
# verified under the contract they were written with, and the absence of a newer
# field is never a failure.

SEALED_DOCUMENTS = {
    "spec_sha256": "When_the_Past_Moves_Especificacion_Ejecutable_V3_3_2026.txt",
    "g1_mp_plan_sha256": "When_the_Past_Moves_Plan_Ejecucion_Realista_G1_MP_V3_3_2026.txt",
}

#: Which sealed documents each manifest schema is required to carry.
SCHEMA_REQUIREMENTS: dict[int, tuple[str, ...]] = {
    1: ("spec_sha256",),
    2: ("spec_sha256", "g1_mp_plan_sha256"),
}

#: Seals that are checked **when present** and never required. The selection
#: configuration did not exist until G2 declared it, so a run that predates it
#: carries `null` there — which means "not yet declared", never "declared as
#: nothing". Requiring it would turn every earlier result red; ignoring it would
#: leave the seal decorative, and a seal nobody checks is not evidence.
OPTIONAL_SEALS = {
    "selection_config_sha256": "config/g2_signals.json",
}

MANIFEST_SOURCES = (G1, G1A, P2, G2A, G2)


def sha256_file(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def check_manifests(root: Path | None = None) -> list[tuple[str, str]]:
    """Each manifest names its governing documents, and the hashes still match.

    A matching hash proves **identity of content, not date of predeclaration**.
    It says the plan has not been edited since the run; it says nothing about
    whether the plan existed before the selection cohort was scored. That needs
    the two external bounds in `.claude/rules/metodo.md`, and it is P4's job.

    `root` exists so the rejection can be tested on a **copy**: proving that a
    changed document fails must not require editing the sealed one.
    """
    base = root or ROOT
    results = base / "reports" / "results"
    failures: list[tuple[str, str]] = []
    live = {
        field: sha256_file(base / name)
        for field, name in (*SEALED_DOCUMENTS.items(), *OPTIONAL_SEALS.items())
    }

    print(f"\n{'manifest seal':42}{'schema':>10}{'document':>30}{'state':>12}")
    for source in MANIFEST_SOURCES:
        path = results / source
        if not path.exists():
            print(f"{source:42}{'-':>10}{'-':>30}{'ABSENT':>12}")
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        manifest = payload.get("manifest", {})
        schema = int(manifest.get("schema_version", 1))
        required = SCHEMA_REQUIREMENTS.get(schema)
        if required is None:
            failures.append((source, f"unknown manifest schema_version {schema}"))
            print(f"{source:42}{schema:>10}{'-':>30}{'UNKNOWN':>12}")
            continue

        optional = tuple(f for f in OPTIONAL_SEALS if manifest.get(f) is not None)
        for field in (*required, *optional):
            stored = manifest.get(field)
            document = SEALED_DOCUMENTS.get(field) or OPTIONAL_SEALS[field]
            label = f"{source} :: {field}"
            if stored is None:
                failures.append((label, f"schema {schema} requires {field}, absent"))
                state = "MISSING"
            elif live[field] is None:
                failures.append((label, f"{document} is not on disk"))
                state = "NO FILE"
            elif stored != live[field]:
                failures.append((
                    label,
                    f"{document} changed since the run (stored {stored[:12]}..., "
                    f"on disk {live[field][:12]}...)",
                ))
                state = "CHANGED"
            else:
                state = "ok"
            print(f"{label:42}{schema:>10}{document[-29:]:>30}{state:>12}")

        # Fields the schema does not require are reported, never demanded.
        for field in SEALED_DOCUMENTS:
            if field not in required and manifest.get(field) is not None:
                print(f"{source + ' :: ' + field:42}{schema:>10}"
                      f"{'(beyond schema)':>30}{'noted':>12}")
    return failures


def main() -> int:
    if not CLAIMS and not EXACT_CLAIMS:
        print("0 tracked claims: the documents state no figures yet.")
        print("Add a row here in the same commit that puts a figure in a document.")
        return 0

    failures: list[tuple[str, str]] = []
    print(f"{'claim':42}{'document':>26}{'artefact':>26}")
    for claim in CLAIMS:
        try:
            actual = claim.read()
        except (KeyError, FileNotFoundError) as exc:
            failures.append((claim.label, f"not found: {exc}"))
            print(f"{claim.label:42}{claim.expected:>26.6g}{'MISSING':>26}   FAIL")
            continue
        ok = abs(actual - claim.expected) <= claim.tolerance
        if not ok:
            failures.append((claim.label, f"{actual:.6g} against {claim.expected:.6g}"))
        print(f"{claim.label:42}{claim.expected:>26.6g}{actual:>26.6g}"
              f"   {'ok' if ok else 'FAIL'}")

    for exact in EXACT_CLAIMS:
        try:
            actual_text = exact.read()
        except (KeyError, FileNotFoundError) as exc:
            failures.append((exact.label, f"not found: {exc}"))
            print(f"{exact.label:42}{exact.expected:>26}{'MISSING':>26}   FAIL")
            continue
        ok = actual_text == exact.expected
        if not ok:
            failures.append((exact.label, f"{actual_text!r} against {exact.expected!r}"))
        print(f"{exact.label:42}{exact.expected:>26}{actual_text:>26}"
              f"   {'ok' if ok else 'FAIL'}")

    total = len(CLAIMS) + len(EXACT_CLAIMS)
    print(f"\n{total - len(failures)}/{total} tracked claims verified")

    seal_failures = check_manifests()
    failures.extend(seal_failures)
    print(f"\nmanifest seals: {'ok' if not seal_failures else 'FAILED'}")

    if failures:
        print("\nfailed:")
        for label, detail in failures:
            print(f"  {label}: {detail}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
