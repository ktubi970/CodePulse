# CodePulse Local — Task Specification Format

Every benchmark task is stored as a self-contained directory under `tasks/<task-id>/`.

## Directory Structure

```text
tasks/<task-id>/
├── manifest.json         # Task metadata, timeout, and fixed test command vector
├── instruction.md        # Prompt instruction provided to the agent model (French)
├── repo/                 # Initial failing repository state (visible and editable by model)
└── verification/         # Protected pytest checks (invisible to model until final verification)
```

## `manifest.json` Schema

```json
{
  "id": "bug_off_by_one",
  "category": "fix_bug",
  "instruction": "instruction.md",
  "repo": "repo",
  "verification": "verification",
  "test_argv": ["{python}", "-m", "pytest", "-q", "repo/tests", "verification"],
  "test_timeout_s": 30.0
}
```

- **`id`**: Unique string identifier matching `[a-z][a-z0-9_]{2,63}`.
- **`category`**: Category name (`fix_bug`, `add_function`, `write_test`, `refactor`, `csv`, `schema_parsing`).
- **`test_argv`**: Fixed argument vector executed with `shell=False`. Must start with `["{python}", "-m", "pytest"]`.
- **`test_timeout_s`**: Hard timeout in seconds for test execution.
