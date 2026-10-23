# Agent instructions for CodePulse Local

Python 3.12+, stdlib first. Runtime dependencies are Streamlit and Plotly (dashboard only); SQLite through `sqlite3`.
Before proposing a change: `ruff check .` and `pytest` must pass (CI: Ubuntu and Windows, Python 3.12 and 3.13).

<!-- PATTERN-DESIGN-START -->
## Architecture and design patterns

Style: a small modular monolith, three packages, no framework. The rules below describe what the code already
does; follow them and do not add abstraction the code does not need (KISS, YAGNI).

### Dependency direction

- `runner/config.py`, `runner/manifests.py`, `runner/storage.py` are leaf modules (stdlib only). Never make them
  import `agent` or `dashboard`: `agent` already imports them, so that would create a cycle.
- `agent/` may import those three leaf modules, never `runner.cli`, `runner.benchmark`, `runner.report` or `dashboard`.
- `runner/cli.py` and `runner/benchmark.py` are the composition root: the only places that build a real
  `OllamaClient` or `ResultStore`.
- `dashboard/` never imports `agent`; it reads results read-only.

### Trust boundary (the invariant that matters most)

- Model output is untrusted data. It selects one of six actions, nothing more. The test command comes from the task
  manifest (`WorkspaceExecutor._execute_pytest_vector`), never from model text.
- One rule for every model-supplied path: `protocol.relative_path` (no absolute path, no `..`, no `:`), then
  `WorkspaceExecutor._resolve_relative_path` (containment after resolving). This covers action fields and patch
  contents alike. `patches.apply_patch` takes the check as `check_path`. It applies it to every path that
  `git apply --numstat` reports, before git writes anything. Rename and copy headers are refused, because numstat
  does not report their source path. Never add a second path rule; git's own refusal is a backstop, not the check.
- `TestResult.passed` requires exit code 0 and a JUnit report with tests > 0 and no failure, error or skip.
  Never relax it to the exit code alone.
- `WorkspaceExecutor.verify()` is the only verdict. It runs these steps, each from a fresh copy of the agent's
  repository at the same path and with the same command:
  1. the manifest's test vector;
  2. each mutant;
  3. the vector again.

  A mutant counts as caught only when a test under `repo/` fails (`TestReport.failed_modules`). Never run mutants
  from another directory or with another command: the agent's tests could tell the runs apart.
  Known residual gap: a test that counts its runs through state outside the workspace and guesses how many mutants a
  task ships can still pass.
- Any change to parsing, paths or verification ships with an adversarial test in `tests/test_verification_integrity.py`.

### Patterns in use

- **Adapter: `agent/ollama.py`.** `OllamaClient` is the only code that talks HTTP to Ollama. It translates every
  failure into `OllamaUnavailable`, `OllamaTimeout`, `OllamaRequestError` or `ModelMissing`. That classification
  decides whether a run counts against the model (`generation_error`) or is excluded (`ollama_unavailable`).
  A new failure mode gets its own exception here plus an explicit `except` in `agent/loop.py`; never widen the
  final `except Exception`. A new endpoint is a method on `OllamaClient`, tested against `MockOllamaHandler`.
- **Command objects with one dispatch point.** Each action is a frozen dataclass in `agent/protocol.py`.
  `WorkspaceExecutor.execute` is the single place that dispatches on the type. The set is closed: do not turn it
  into a registry or a Strategy hierarchy. Adding an action means changing all of the following together:
  - the dataclass, `_REQUIRED_FIELDS` and the `Action` union;
  - an executor method and its branch in `execute`;
  - the system prompt in `agent/prompt.py`;
  - tests.
- **Repository: `runner/storage.py`.** `ResultStore` owns the SQLite schema. Writes go through
  `start_run`, `append_action` and `finish_run`. A new query is a new method on `ResultStore`, not inline SQL.
  Connections are only opened through `_connect()`.
- **Constructor injection, no container.** I/O collaborators are parameters: `BenchmarkRunner(config, client)` and
  `run_agent(client=..., store=...)`. Tests pass the hand-written fakes `ScriptedClient`, `FakeOllamaClient` and
  `MockOllamaHandler`. Reuse them rather than `unittest.mock`.
- **Immutable value objects.** Data carriers are `@dataclass(frozen=True, slots=True)`, as all 20 current ones are.
- **Context managers for every resource.** Use them for temp workspaces (`WorkspaceExecutor`), SQLite connections
  (`_connect()`, `closing()`) and HTTP connections (`finally: conn.close()`). A leaked handle locks files on
  Windows (WinError 32) and CI runs on Windows.

### Deliberately not used

- Strategy or a plugin registry for actions: there are six, and the set is part of the benchmark protocol.
- Observer or an event bus: the runner is one synchronous process.
- Unit of Work: each storage call is one short transaction.
- An ORM: two tables.
- Abstract base classes for a single implementation.
- A DI framework.

### Known deviations (fix when touching the code, do not copy)

- `dashboard/data.py` queries SQLite with its own SQL instead of `ResultStore`, so the schema is known in two places.
  `latest_per_pair` also exists twice: `runner/report.py` (dicts) and `dashboard/data.py` (`DashboardRun`).
- `client` is typed `Any` in `BenchmarkRunner.__init__` and `run_agent`. It should be a `typing.Protocol` that
  covers `version`, `require_model`, `load_model` and `chat`.
- Run statuses are bare strings in `agent/loop.py`, `runner/report.py` and `docs/result-format.md`. Keep the three
  in sync until they become a `StrEnum`.
<!-- PATTERN-DESIGN-END -->
