from pathlib import Path

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


def test_corpus_has_exact_expected_ids() -> None:
    discovered = discover_tasks(Path("tasks"))
    assert set(discovered.keys()) == EXPECTED_IDS


def test_every_initial_repository_fails_its_fixed_tests() -> None:
    tasks = discover_tasks(Path("tasks"))
    for task_id, manifest in tasks.items():
        with WorkspaceExecutor.create(manifest, test_timeout_s=manifest.test_timeout_s) as executor:
            result = executor.final_test()
        assert result.exit_code != 0, f"Task '{task_id}' initial state should fail fixed tests, but passed!"
