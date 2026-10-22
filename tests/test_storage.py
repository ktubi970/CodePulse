from pathlib import Path

from runner.storage import ActionRecord, ResultStore, RunRecord


def test_store_round_trips_authoritative_final_evidence(tmp_path: Path) -> None:
    store = ResultStore(tmp_path / "results.sqlite3")
    run = RunRecord.new(
        model_tag="local:test",
        model_digest="abc",
        ollama_version="0.test",
        task_id="bug_off_by_one",
        category="fix_bug",
        parameters={"temperature": 0, "max_turns": 12},
        instruction="Fix the boundary.",
        is_demo=False,
    )
    store.start_run(run)
    store.append_action(
        ActionRecord.new(run.run_id, 1, "read_file", {"path": "a.py"}, {"ok": True})
    )
    store.finish_run(
        run.run_id,
        status="success",
        success=True,
        duration_s=1.25,
        turns=1,
        test_runs=1,
        final_patch="--- a/a.py\n+++ b/a.py\n",
        final_test_exit_code=0,
        final_test_stdout="1 passed",
        final_test_stderr="",
        error_type=None,
        error_message=None,
    )

    loaded = store.get_run(run.run_id)
    assert loaded is not None
    assert loaded["success"] == 1
    assert loaded["final_test_exit_code"] == 0
    assert loaded["actions"][0]["action_type"] == "read_file"


def test_store_releases_the_database_file(tmp_path: Path) -> None:
    # A leaked connection keeps the file locked on Windows (WinError 32).
    db = tmp_path / "results.sqlite3"
    store = ResultStore(db)
    run = RunRecord.new("m", "d", "v", "t", "c", {}, "i")
    store.start_run(run)
    store.finish_run(run.run_id, status="tests_failed", success=False, duration_s=0.0, turns=0, test_runs=1)
    store.get_run(run.run_id)
    store.list_runs()
    db.unlink()
    assert not db.exists()


def test_started_run_remains_visible_before_finalization(tmp_path: Path) -> None:
    store = ResultStore(tmp_path / "results.sqlite3")
    run = RunRecord.new(
        model_tag="m",
        model_digest="d",
        ollama_version="v",
        task_id="t",
        category="c",
        parameters={},
        instruction="i",
        is_demo=False,
    )
    store.start_run(run)
    loaded = store.get_run(run.run_id)
    assert loaded is not None
    assert loaded["status"] == "running"
