# CodePulse Local — Task Specification Format

Every benchmark task is stored as a self-contained directory under `tasks/<task-id>/`.

## Directory Structure

```text
tasks/<task-id>/
├── manifest.json         # Task metadata, timeout, and fixed test command vector
├── instruction.md        # Instruction given to the agent model (English)
├── repo/                 # Initial failing repository state (visible and editable by model)
├── verification/         # Hidden pytest checks, copied outside the model's editable root
├── solution/             # Reference solution overlaid on repo/ (never shown to the model)
└── mutants/<name>/       # Optional: buggy variants the agent's own tests must catch
```

- Paths in `instruction.md` are relative to `repo/`, because that is the root the agent sees
  (write `src/window.py`, not `repo/src/window.py`).
- Every task needs a `solution/`. `validate-tasks` and `tests/test_corpus.py` check that the
  initial state fails and that the reference solution passes, so a broken verification file
  is caught instead of silently lowering every model's score.
- Test-writing tasks ship `mutants/`. After the final run passes, each mutant is overlaid on a
  fresh copy of the agent's repository, at the same path, and the same test command runs again.
  A mutant is caught only if one of the agent's tests (under `repo/`) fails; the hidden tests fail
  on every mutant and do not count. If any mutant is not caught, the run fails with status
  `weak_tests`. The real run is then repeated, so a test that behaves differently on later runs
  fails it. This stops an agent from "fixing" a failing test by deleting its assertions, or by
  writing a test that only detects the mutant workspace.

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
  The harness runs it as `python -I -B -m pytest --noconftest -p no:cacheprovider -o pythonpath=repo --junitxml=<report> <rest of test_argv>`.
- **`solution`**, **`mutants`** (optional keys): directory names, defaulting to `solution/` and `mutants/` when present.
- **`test_timeout_s`**: Hard timeout in seconds for test execution.
