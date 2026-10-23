from pathlib import Path
import re

import pytest

from agent.executor import WorkspaceExecutor
from runner.manifests import discover_tasks

EXPECTED_IDS = {
    "bug_off_by_one",
    "bug_cache_key",
    "feature_slugify",
    "feature_chunked",
    "test_parse_bool",
    "test_safe_divide",
    "refactor_pricing",
    "refactor_normalize_record",
    "csv_clean_contacts",
    "csv_sales_summary",
    "parse_config_version",
    "parse_event_payload",
}

TASKS = discover_tasks(Path("tasks"))


def test_corpus_has_exact_expected_ids() -> None:
    assert set(TASKS.keys()) == EXPECTED_IDS


def test_task_files_use_lf_line_endings() -> None:
    # File sizes are part of the prompt: CRLF checkouts would change it per platform.
    crlf = [
        p.as_posix()
        for p in Path("tasks").rglob("*")
        if p.suffix in {".py", ".md", ".json"} and b"\r\n" in p.read_bytes()
    ]
    assert crlf == []


@pytest.mark.parametrize("task_id", sorted(EXPECTED_IDS))
def test_instruction_paths_match_the_agent_workspace(task_id: str) -> None:
    # The agent sees the repository root, so `repo/src/x.py` in an instruction is a dead path.
    manifest = TASKS[task_id]
    paths = re.findall(r"`([\w./-]+\.py)`", manifest.instruction())
    assert paths, f"Task '{task_id}' instruction names no file"
    for path in paths:
        assert (manifest.repo_path / path).is_file(), f"'{path}' in {task_id} does not exist in the workspace"


@pytest.mark.parametrize("task_id", sorted(EXPECTED_IDS))
def test_initial_repository_fails_its_fixed_tests(task_id: str) -> None:
    manifest = TASKS[task_id]
    with WorkspaceExecutor.create(manifest, test_timeout_s=manifest.test_timeout_s) as executor:
        result = executor.final_test()
    assert result.exit_code != 0, f"Task '{task_id}' initial state should fail fixed tests, but passed!"


@pytest.mark.parametrize("task_id", sorted(EXPECTED_IDS))
def test_reference_solution_passes_verification(task_id: str) -> None:
    # Without this check, a broken verification file is indistinguishable from a hard task.
    manifest = TASKS[task_id]
    assert manifest.solution_path is not None, f"Task '{task_id}' has no reference solution"
    with WorkspaceExecutor.create(manifest, test_timeout_s=manifest.test_timeout_s) as executor:
        executor.overlay(manifest.solution_path)
        result = executor.final_test()
        survivors = executor.surviving_mutants()
    assert result.passed, f"Reference solution for '{task_id}' fails:\n{result.stdout}{result.stderr}"
    assert survivors == [], f"Reference tests for '{task_id}' miss mutants: {survivors}"
