"""G1: the whole chain, once, for real.

    as-of state -> forecast -> immutable prediction -> eligible label
                -> signals -> recommendation -> manifest

What this is for is not a number. It is to show that the chain exists, that it
refuses to run on information it should not have, and that it fails safely: a
missing label produces `ESPERAR_MADUREZ`, not a fabricated score.

Two modalities, and they are never mixed in the output:

* **`historical_replay`** walks earlier cuts to issue the predictions that a
  performance signal needs in order to exist at all. A replay reconstructed
  today does not become a run that happened back then.
* **`observed_run`** is the live cut. On a first run its honest outcome is
  usually `ESPERAR_MADUREZ`, because the label for the week just forecast has
  not matured — and recording that is the point rather than an embarrassment.

Everything declared here is declared *here*, in code, before the confirmatory
cohort exists: the maturity policy, the calibration window, the thresholds and
the model. They are written into the run's config so that what produced a
recommendation can never be in doubt.
"""

from __future__ import annotations

import argparse
from datetime import UTC, date, datetime, timedelta

import pandas as pd

from revmon import evidence, sources
from revmon.evidence import Modality, RunManifest
from revmon.forecasting import NAIVE, ForecastError, calibrate_scale, forecast
from revmon.monitoring import (
    Information,
    Thresholds,
    coverage_drop,
    recent_loss,
    recommend,
    revision_share,
)
from revmon.panel import as_of_view, fetch_triangle_as_of
from revmon.temporal import Completeness, MaturityPolicy, ReplayMode

DECLARED_IN = "G1 development run, 2026-10-16, before any confirmatory cohort exists"

#: 45 days is one point on the pre-declared sensitivity grid (45/60/90), not an
#: inherited truth. The value used in the confirmatory evaluation is fixed at
#: the freeze and reported with its sensitivity.
MATURITY = MaturityPolicy(days=45, declared_in=DECLARED_IN)

#: Retrospective, and it ends well before any cut this script scores. A scale
#: computed over the evaluated period would move with what it is scaling.
CALIBRATION = (date(2024, 11, 19), date(2025, 6, 30))

THRESHOLDS = Thresholds(
    loss_alarm=2.0,
    revision_share_alarm=0.25,
    coverage_drop_alarm=2.0,
    min_mature_labels=4,
    declared_in=DECLARED_IN,
)

#: The arm used for the single recommendation G1 produces. The other three exist
#: and are exercised in G2; running all four here would invite reading a
#: four-way comparison into a chain that was built to show the chain works.
ARM = Information(revision=True, coverage=True)


def prediction_id(f_dict: dict, signal: str, geography: str) -> str:
    """Deterministic, so re-running a cut cannot produce a second prediction."""
    stem = "|".join(
        [signal, geography, f_dict["model"], f_dict["issued_for_cut"], f_dict["target_week"]]
    )
    return f"{f_dict['issued_for_cut']}-{evidence.sha256_text(stem)[:12]}"


def run_cut(
    cut: date,
    *,
    modality: str,
    scale=None,
    coverage_state: pd.DataFrame | None = None,
) -> dict:
    """One link of the chain, end to end, at one cut."""
    triangle, provenance = fetch_triangle_as_of(cut)
    if triangle.empty:
        return {
            "cut": str(cut),
            "modality": modality,
            "completeness": Completeness.DATA_UNAVAILABLE.value,
            "recommendation": recommend(
                information=ARM,
                thresholds=THRESHOLDS,
                completeness=Completeness.DATA_UNAVAILABLE,
                loss=None,
                mature_labels=0,
                revisions=None,
                coverage_fall=None,
            ).as_dict(),
        }

    state, completeness = as_of_view(triangle, cut, ReplayMode.PUBLIC_REPLAY)

    record: dict = {
        "cut": str(cut),
        "modality": modality,
        "completeness": completeness.value,
        "state_weeks": int(len(state)),
        "provenance": provenance.as_dict() if provenance else None,
    }

    try:
        issued = forecast(state, cut, model=NAIVE)
        stored, written = evidence.record_prediction(
            {
                **issued.as_dict(),
                "prediction_id": prediction_id(
                    issued.as_dict(), sources.TARGET_SIGNAL, sources.GEO_TYPE
                ),
                "signal": sources.TARGET_SIGNAL,
                "geo_type": sources.GEO_TYPE,
                "modality": modality,
                "data_vintage_id": str(state["vintage_id"].max()),
                "issued_at": datetime.now(UTC).isoformat(),
            }
        )
        record["prediction"] = stored
        # False means this cut had already issued a forecast and it was kept.
        # That is invariant I4 holding, not a no-op.
        record["prediction_was_written_now"] = written
    except ForecastError as exc:
        record["forecast_error"] = str(exc)
        record["recommendation"] = recommend(
            information=ARM,
            thresholds=THRESHOLDS,
            completeness=Completeness.INSUFFICIENT_EVIDENCE,
            loss=None,
            mature_labels=0,
            revisions=revision_share(triangle),
            coverage_fall=coverage_drop(coverage_state),
        ).as_dict()
        return record

    loss, mature = (None, 0)
    if scale is not None:
        # Only predictions issued strictly before this cut may be scored at it.
        # Scoring a forecast against its own cut would be scoring hindsight.
        past = pd.DataFrame(
            [p for p in load_predictions() if p["issued_for_cut"] < str(cut)]
        )
        loss, mature = recent_loss(state, past, scale, MATURITY, cut)

    revisions = revision_share(triangle)
    fall = coverage_drop(coverage_state)

    record["recommendation"] = recommend(
        information=ARM,
        thresholds=THRESHOLDS,
        completeness=completeness,
        loss=loss,
        mature_labels=mature,
        revisions=revisions,
        coverage_fall=fall,
    ).as_dict()
    return record


def load_predictions() -> list[dict]:
    """Every prediction issued so far. Read-only; nothing here rewrites one."""
    import json

    if not evidence.PREDICTIONS.exists():
        return []
    return [
        json.loads(p.read_text(encoding="utf-8"))
        for p in sorted(evidence.PREDICTIONS.glob("*.json"))
    ]


def build_figure(triangle, coverage_state, predictions: list[dict], recent_weeks: int = 8):
    """The one picture: a forecast that never moved, against a target that did.

    Three panels on shared time, with separate axes and no causal arrows. The
    middle one is the point of the project — the same event week restated across
    its successive publications — and the bottom one is the third mechanism,
    reporting coverage, kept on its own scale so nobody reads it as admissions.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    frame = triangle.copy()
    frame["event_week_end"] = pd.to_datetime(frame["event_week_end"])
    frame["source_report_date"] = pd.to_datetime(frame["source_report_date"])

    first = frame[frame["is_first_release"].astype(bool)].sort_values("event_week_end")
    latest = (
        frame.sort_values("release_index")
        .groupby("event_week_end", as_index=False)
        .last()
        .sort_values("event_week_end")
    )
    window = latest["event_week_end"].max() - pd.Timedelta(weeks=52)
    first = first[first["event_week_end"] >= window]
    latest = latest[latest["event_week_end"] >= window]

    fig, axes = plt.subplots(3, 1, figsize=(11, 10), sharex=False)

    ax = axes[0]
    ax.plot(first["event_week_end"], first["value"], label="as first published", lw=1.4)
    ax.plot(latest["event_week_end"], latest["value"], label="as published now", lw=1.4)
    issued = pd.DataFrame(predictions)
    if not issued.empty:
        issued["target_week"] = pd.to_datetime(issued["target_week"])
        issued = issued[issued["target_week"] >= window]
        ax.scatter(
            issued["target_week"], issued["y_pred"], s=26, zorder=3,
            label="forecast as issued, never rewritten",
        )
    ax.set_title("The target moved after the forecast was issued")
    ax.set_ylabel("weekly flu admissions")
    ax.legend(fontsize=8)

    ax = axes[1]
    recent = sorted(frame["event_week_end"].unique())[-recent_weeks:]
    for week in recent:
        serie = frame[frame["event_week_end"] == week].sort_values("source_report_date")
        ax.plot(
            serie["source_report_date"], serie["value"],
            marker="o", ms=3, lw=1.2, label=pd.Timestamp(week).strftime("%d %b"),
        )
    ax.set_title(f"The same {recent_weeks} event weeks, restated across their publications")
    ax.set_ylabel("value at each publication")
    ax.set_xlabel("publication date (source_report_date)")
    ax.legend(fontsize=7, ncol=4, title="event week ending", title_fontsize=7)

    ax = axes[2]
    if coverage_state is not None and not coverage_state.empty:
        cov = coverage_state.copy()
        cov["event_week_end"] = pd.to_datetime(cov["event_week_end"])
        cov = cov[cov["event_week_end"] >= window].sort_values("event_week_end")
        ax.plot(cov["event_week_end"], cov["value"], lw=1.4, color="0.35")
        ax.set_ylabel("% of facilities reporting")
    else:
        ax.text(0.5, 0.5, "coverage unavailable at this cut", ha="center", va="center")
    ax.set_title("Reporting coverage, on its own axis: a third mechanism, not a cause")
    ax.set_xlabel("event week ending")

    fig.tight_layout()
    path = evidence.FIGURES / "01_forecast_vs_revisions.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replay-cuts", type=int, default=14, help="earlier cuts to replay")
    parser.add_argument(
        "--replay-ends-weeks-ago",
        type=int,
        default=8,
        help="leave this much room so replayed labels can have matured",
    )
    args = parser.parse_args()

    today = datetime.now(UTC).date()
    manifest = RunManifest.start(
        decision_as_of=str(today),
        modality=Modality.OBSERVED_RUN,
        config={
            "maturity_policy": {
                "days": MATURITY.days,
                "label_choice": MATURITY.label_choice,
                "declared_in": MATURITY.declared_in,
            },
            "calibration_window": [str(CALIBRATION[0]), str(CALIBRATION[1])],
            "thresholds": THRESHOLDS.as_dict(),
            "model": NAIVE,
            "arm": ARM.arm,
            "signal": sources.TARGET_SIGNAL,
            "coverage_signal": sources.COVERAGE_PCT_SIGNAL,
            "geo_type": sources.GEO_TYPE,
        },
    )

    # The loss scale, computed once in the declared retrospective window.
    print("calibrating the loss scale ...", flush=True)
    calibration_state, _ = fetch_triangle_as_of(CALIBRATION[1])
    scale = calibrate_scale(
        as_of_view(calibration_state, CALIBRATION[1], ReplayMode.PUBLIC_REPLAY)[0],
        window_from=CALIBRATION[0],
        window_to=CALIBRATION[1],
        policy=MATURITY,
    )
    print(f"  s_dev = {scale.s_dev} over {scale.pairs} pairs", flush=True)

    # Coverage, as of today. Its own signal, on its own axis.
    print("fetching reporting coverage ...", flush=True)
    coverage_triangle, _ = fetch_triangle_as_of(today, signal=sources.COVERAGE_PCT_SIGNAL)
    coverage_state = (
        as_of_view(coverage_triangle, today, ReplayMode.PUBLIC_REPLAY)[0]
        if not coverage_triangle.empty
        else None
    )

    # Labelled replay: issues the predictions a performance signal needs.
    replay_end = today - timedelta(weeks=args.replay_ends_weeks_ago)
    cuts = [replay_end - timedelta(weeks=k) for k in range(args.replay_cuts, 0, -1)]
    replayed = []
    for cut in cuts:
        print(f"replay {cut} ...", flush=True)
        replayed.append(run_cut(cut, modality=Modality.HISTORICAL_REPLAY, scale=scale))

    # The live cut. This is the run that actually happened.
    print(f"observed run {today} ...", flush=True)
    live = run_cut(
        today, modality=Modality.OBSERVED_RUN, scale=scale, coverage_state=coverage_state
    )

    manifest.state = "completed"
    actions = pd.Series([r["recommendation"]["action"] for r in replayed])

    payload = {
        "manifest": manifest.as_dict(),
        "loss_scale": scale.as_dict(),
        "observed_run": live,
        "historical_replay": {
            "cuts": replayed,
            "action_counts": actions.value_counts().to_dict(),
            "note": (
                "Reconstructed today from versions the source declares were published "
                "at each cut. This is not evidence that the system ran on those dates."
            ),
        },
    }
    print("drawing the figure ...", flush=True)
    live_triangle, _ = fetch_triangle_as_of(today)
    figure_path = build_figure(live_triangle, coverage_state, load_predictions())
    payload["figure"] = str(figure_path.relative_to(sources.ROOT))

    path = evidence.write_json_atomic(
        evidence.RESULTS / "01_vertical_slice.json", payload
    )

    print()
    print("=" * 72)
    print(f"s_dev                 : {scale.s_dev} ({scale.pairs} pairs)")
    print(f"observed run           : {live['recommendation']['action']}")
    print(f"  reason               : {live['recommendation']['reason']}")
    print(f"replayed cuts          : {len(replayed)}")
    for action, count in actions.value_counts().items():
        print(f"  {action:20} {count}")
    print(f"predictions on disk    : {len(load_predictions())}")
    print("=" * 72)
    print(f"wrote {path.relative_to(sources.ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
