from pathlib import Path

from runner.cli import main
from runner.report import render_markdown
from runner.storage import ResultStore, RunRecord


def _record(store: ResultStore, model: str, task: str, status: str, duration: float, demo: bool = False) -> None:
    run = RunRecord.new(model, "digest", "0.40.8", task, "fix_bug", {"temperature": 0.0, "max_turns": 12}, "i", demo)
    store.start_run(run)
    store.finish_run(
        run.run_id, status=status, success=status == "success", duration_s=duration, turns=3, test_runs=1
    )


def _store(tmp_path: Path) -> ResultStore:
    store = ResultStore(tmp_path / "results.sqlite3")
    _record(store, "small:1b", "task_a", "tests_failed", 9.0)
    _record(store, "small:1b", "task_a", "success", 4.0)  # re-run replaces the failure
    _record(store, "small:1b", "task_b", "response_timeout", 120.0)
    _record(store, "big:3b", "task_a", "success", 2.0)
    _record(store, "big:3b", "task_b", "success", 6.0)
    _record(store, "demo:1b", "task_a", "success", 1.0, demo=True)  # never reported
    return store


def test_report_ranks_latest_real_runs(tmp_path: Path) -> None:
    report = render_markdown(_store(tmp_path).finished_runs())
    lines = report.splitlines()
    big = next(i for i, line in enumerate(lines) if line.startswith("| 1 | `big:3b`"))
    small = next(i for i, line in enumerate(lines) if line.startswith("| 2 | `small:1b`"))
    assert big < small
    assert "| 2 | `small:1b` | 1/2 | 50% |" in report
    assert "demo:1b" not in report
    assert "4 runs" in report  # 5 real runs, minus the superseded failure


def test_report_lists_failure_modes(tmp_path: Path) -> None:
    report = render_markdown(_store(tmp_path).finished_runs())
    assert "| `response_timeout` | 1 |" in report
    assert "tests_failed" not in report  # superseded by the successful re-run


def test_report_handles_empty_database(tmp_path: Path) -> None:
    assert "No finished runs" in render_markdown(ResultStore(tmp_path / "empty.sqlite3").finished_runs())


def test_cli_report_writes_utf8_file(tmp_path: Path) -> None:
    _store(tmp_path)
    config = tmp_path / "codepulse.toml"
    config.write_text('[benchmark]\nmodels = ["m"]\nresult_db = "results.sqlite3"\n', encoding="utf-8")
    output = tmp_path / "results.md"

    assert main(["--config", str(config), "report", "--output", str(output)]) == 0
    assert "`big:3b`" in output.read_text(encoding="utf-8")
