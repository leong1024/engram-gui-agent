from pathlib import Path

import pytest
from typer.testing import CliRunner

from artemis.interfaces.cli.main import app
from tests.unit.app_memory.fixtures import screens
from tests.unit.app_memory.fixtures.parts import CLOCK
from tests.unit.app_memory.fixtures.traces import MapView, Trace, tap

runner = CliRunner(env={"COLUMNS": "200"})


@pytest.fixture
def traces(tmp_path: Path) -> Path:
    run = Trace(tmp_path).session("s1", "completed")
    run.step(screens.clock("Alarm"), tap("clock:id/nav_timer"))
    run.step(screens.clock("Timer"), tap("clock:id/nav_stopwatch"))
    run.step(screens.clock("Stopwatch"))
    return tmp_path


def invoke(*args: str):
    return runner.invoke(app, ["app-memory", *args])


def test_help_lists_backfill_and_stats():
    result = invoke("--help")
    assert result.exit_code == 0
    assert "backfill" in result.output
    assert "stats" in result.output


def test_backfill_one_session_reports_its_outcome(traces):
    result = invoke("backfill", "--session", "s1", "--path", str(traces))

    assert result.exit_code == 0, result.output
    assert "s1" in result.output and "completed" in result.output
    view = MapView(traces / "app_memory.db")
    assert view.session("s1") == ("finalized", "completed")
    assert [status for _, _, status in view.observations("s1")] == ["confirmed"] * 2


def test_backfill_refuses_an_unknown_session(traces):
    result = invoke("backfill", "--session", "nope", "--path", str(traces))

    assert result.exit_code == 1
    assert not (traces / "app_memory.db").exists()


@pytest.mark.parametrize("args", [[], ["--session", "s1", "--all"]])
def test_backfill_needs_exactly_one_selector(traces, args):
    assert invoke("backfill", *args, "--path", str(traces)).exit_code == 2


def test_stats_prints_the_counts_of_each_map(traces):
    assert invoke("backfill", "--all", "--path", str(traces)).exit_code == 0

    result = invoke("stats", "--path", str(traces))

    assert result.exit_code == 0, result.output
    row = next(line for line in result.output.splitlines() if CLOCK in line)
    cells = [cell.strip() for cell in row.split("│")[2:8]]
    assert cells == ["1", "3", "2", "2", "0", "0"]


def test_stats_without_a_map_says_so(tmp_path):
    result = invoke("stats", "--path", str(tmp_path))

    assert result.exit_code == 0
    assert "No app memory" in result.output
