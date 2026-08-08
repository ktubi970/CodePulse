# CodePulse Local — SQLite Result Storage Schema

Results are persisted in SQLite (`results/codepulse.sqlite3`) using transactional writes and foreign key constraints.

## `runs` Table

Stores top-level metadata and authoritative test results for each benchmark run.

| Column | Type | Description |
|---|---|---|
| `run_id` | TEXT (UUID4) | Primary Key |
| `is_demo` | INTEGER (0/1) | Flag indicating fictional demo run |
| `model_tag` | TEXT | Ollama model tag (e.g. `qwen2.5:1.5b`) |
| `model_digest` | TEXT | Ollama model sha256 digest |
| `ollama_version` | TEXT | Installed Ollama server version |
| `task_id` | TEXT | Benchmark task identifier |
| `category` | TEXT | Task category |
| `parameters_json` | TEXT (JSON) | Serialized budget and parameters |
| `instruction` | TEXT | Full instruction prompt |
| `created_at` | TEXT (ISO-8601) | Run start timestamp |
| `finished_at` | TEXT (ISO-8601) | Run completion timestamp |
| `status` | TEXT | Terminal status (`success`, `tests_failed`, etc.) |
| `success` | INTEGER (0/1) | Objective success flag based on final pytest exit code 0 |
| `duration_s` | REAL | Total execution duration in seconds |
| `turns` | INTEGER | Number of turns consumed |
| `test_runs` | INTEGER | Number of pytest invocations |
| `final_patch` | TEXT | Unified diff patch of modifications |
| `final_test_exit_code` | INTEGER | Fresh final pytest process exit code |
| `final_test_stdout` | TEXT | Pytest stdout output |
| `final_test_stderr` | TEXT | Pytest stderr output |
| `error_type` | TEXT | Exception class name if failed |
| `error_message` | TEXT | Exception diagnostic message |
| `platform_system` | TEXT | Operating system platform |
| `python_version` | TEXT | Python runtime version |

## `actions` Table

Stores turn-by-turn action requests and observations.

| Column | Type | Description |
|---|---|---|
| `run_id` | TEXT | Foreign key referencing `runs.run_id` |
| `turn` | INTEGER | Turn index (1-based) |
| `action_type` | TEXT | Action type (`list_files`, `read_file`, `apply_patch`, `run_tests`, `finish`) |
| `request_json` | TEXT (JSON) | Request arguments |
| `result_json` | TEXT (JSON) | Execution outcome observations |
| `created_at` | TEXT (ISO-8601) | Action timestamp |
| `duration_s` | REAL | Action execution time in seconds |
