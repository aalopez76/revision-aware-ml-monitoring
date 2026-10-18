"""One record per execution, and reconciliation that counts weeks not files.

This covers a defect, so it is tested in both directions. The rule the project
makes about operation is small and checkable:

> If a run did not happen there is no file. **If a run did happen its record
> stays.**

The second half failed until now: records were keyed by ISO week, so a second
run in the same week overwrote the first. Nothing was lost, because the file is
versioned and the bot commits every run, but the working tree then showed one
execution where two had happened — and `/registro-semanal` reconciles against
the files, not against git history.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from revmon import evidence

ROOT = Path(__file__).resolve().parents[1]


def load_script(relative: str, name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def capture():
    return load_script("scripts/weekly_capture.py", "weekly_capture")


@pytest.fixture
def estado():
    return load_script(".claude/hooks/estado_sesion.py", "estado_sesion")


# --- the execution identity -------------------------------------------------


def test_a_runner_execution_is_named_by_run_and_attempt(capture, monkeypatch):
    monkeypatch.setenv("GITHUB_RUN_ID", "39106257967")
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "2")
    run, attempt, on_a_runner = capture.execution_id()
    assert (run, attempt, on_a_runner) == ("39106257967", "2", True)
    assert capture.RECORD_PATTERN.format(
        year=2026, week=42, run=run, attempt=attempt
    ) == "2026-W42__39106257967__a2.json"


def test_a_missing_attempt_defaults_to_one_rather_than_empty(capture, monkeypatch):
    """Actions always sets it, but a name with `a` and nothing after is not a name."""
    monkeypatch.setenv("GITHUB_RUN_ID", "1")
    monkeypatch.delenv("GITHUB_RUN_ATTEMPT", raising=False)
    assert capture.execution_id()[1] == "1"
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "")
    assert capture.execution_id()[1] == "1"


def test_a_local_execution_does_not_depend_on_github_variables(capture, monkeypatch):
    monkeypatch.delenv("GITHUB_RUN_ID", raising=False)
    monkeypatch.delenv("GITHUB_RUN_ATTEMPT", raising=False)
    run, attempt, on_a_runner = capture.execution_id()
    assert on_a_runner is False
    assert run.startswith("local-")
    assert attempt == "1"


def test_two_local_executions_never_share_a_name(capture, monkeypatch):
    """Two runs in the same second must be two records, not one overwriting one."""
    monkeypatch.delenv("GITHUB_RUN_ID", raising=False)
    names = {capture.execution_id()[0] for _ in range(50)}
    assert len(names) == 50


# --- write once: no silent overwrite, idempotent for one execution ----------


def test_the_same_execution_writing_twice_keeps_the_first_record(tmp_path):
    path = tmp_path / "2026-W42__39106257967__a1.json"
    first, wrote_first = evidence.write_json_once(path, {"run_at": "first"})
    second, wrote_second = evidence.write_json_once(path, {"run_at": "second"})

    assert (wrote_first, wrote_second) == (True, False)
    assert first["run_at"] == "first"
    assert second["run_at"] == "first", "the later write silently replaced the record"
    assert json.loads(path.read_text(encoding="utf-8"))["run_at"] == "first"


def test_two_executions_in_one_week_coexist(tmp_path):
    """The defect, directly: both records must survive side by side."""
    week = tmp_path / "reports" / "weekly"
    week.mkdir(parents=True)
    for run in ("38992358050", "39106257967"):
        evidence.write_json_once(
            week / f"2026-W42__{run}__a1.json", {"iso_week": 42, "runner": run}
        )

    files = sorted(week.glob("*.json"))
    assert len(files) == 2
    runners = {json.loads(f.read_text(encoding="utf-8"))["runner"] for f in files}
    assert runners == {"38992358050", "39106257967"}


# --- reconciliation: weeks, not files ---------------------------------------


def test_the_week_is_read_from_both_naming_schemas(estado):
    assert estado.semana_de(Path("2026-W42.json")) == (2026, 42)
    assert estado.semana_de(Path("2026-W42__39106257967__a1.json")) == (2026, 42)
    assert estado.semana_de(Path("2026-W07__local-20261018T070347Z-ab12cd__a1.json")) == (
        2026,
        7,
    )


def test_an_unparseable_name_is_reported_as_such_not_as_a_week(estado):
    """The old parser raised on the new name and returned 0 — it failed open."""
    for name in ("notes.json", "2026-42.json", "W42-2026.json", "2026-WXX.json"):
        assert estado.semana_de(Path(name)) is None


def test_extra_runs_in_one_week_do_not_hide_a_gap(estado):
    """Adding runs to already-covered weeks must not reduce the gap count.

    Asserted as a relationship rather than a literal, because the number of
    elapsed weeks depends on the weekday the suite runs on and a test that
    passes only on Sundays is worse than no test.
    """
    this_week = datetime.now(UTC).isocalendar()
    earlier = datetime.fromordinal(
        datetime.now(UTC).date().toordinal() - 21
    ).isocalendar()

    two_weeks_covered = [
        Path(f"{earlier.year}-W{earlier.week:02d}__a__a1.json"),
        Path(f"{this_week.year}-W{this_week.week:02d}__c__a1.json"),
    ]
    with_extra_runs = two_weeks_covered + [
        Path(f"{earlier.year}-W{earlier.week:02d}__b__a1.json"),
        Path(f"{this_week.year}-W{this_week.week:02d}__d__a1.json"),
    ]

    gap = estado.semanas_faltantes(two_weeks_covered)
    assert gap > 0, "three weeks apart with two covered must leave a gap"
    assert estado.semanas_faltantes(with_extra_runs) == gap, (
        "extra runs within covered weeks changed the gap count, so files are "
        "being counted as weeks again"
    )


def test_a_single_covered_week_reports_no_gap(estado):
    this_week = datetime.now(UTC).isocalendar()
    only_now = [Path(f"{this_week.year}-W{this_week.week:02d}__run__a1.json")]
    assert estado.semanas_faltantes(only_now) == 0


def test_no_records_is_not_a_gap_count(estado):
    assert estado.semanas_faltantes([]) == 0
