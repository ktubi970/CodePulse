# CodePulse Local — Design

> **Original design document (July 2026).** Kept to show the initial reasoning.
> The first benchmark built from it scored 0/218 runs, and several decisions
> changed as a result. Where this document and the code disagree, the code and
> the [README](../README.md) are authoritative. Main changes since:
>
> - a sixth action, `write_file`, because small models could not produce valid
>   unified diffs (0 of 352 applied);
> - the parser accepts every field the JSON schema allows instead of rejecting
>   extra ones;
> - success requires a clean JUnit report from an isolated `python -I` pytest run
>   with `--noconftest`, not only exit code zero;
> - every task ships a reference solution, and test-writing tasks ship mutants;
> - task instructions are in English and use repository-relative paths.

## 1. Purpose and scope

CodePulse Local is a reproducible, visual benchmark for small language
models acting as coding agents through a local Ollama server. It answers one
question:

> Under identical constraints, which local models solve small Python
> programming tasks most effectively?

The MVP contains twelve synthetic Python tasks, an iterative JSON action
protocol, a confined executor, a benchmark runner, durable local results, and
a Streamlit/Plotly dashboard. All prompts, task repositories, actions, test
outputs, patches, and result files remain on the machine.

CodePulse Local never pulls a model and never calls a hosted API. Its only
model endpoint is an explicitly validated loopback URL, defaulting to
`http://127.0.0.1:11434`.

## 2. Non-goals

- General-purpose shell access for the model.
- Benchmarking arbitrary or untrusted third-party repositories.
- Container, VM, or kernel-level sandboxing.
- Claiming that twelve synthetic tasks predict performance on all software.
- Redistributing model weights or applying the MIT license to model weights.
- Publishing results or source code to GitHub or another external service.

## 3. Design choice

The harness uses a model-independent JSON action protocol on Ollama's
`/api/chat` endpoint. It does not use native tool calling because several
installed models do not advertise that capability. A common protocol avoids
giving tool-capable models a structural advantage.

One model response produces exactly one action:

```json
{"action": "list_files"}
```

```json
{"action": "read_file", "path": "src/example.py"}
```

```json
{"action": "apply_patch", "patch": "--- a/src/example.py\n+++ b/src/example.py\n@@ ..."}
```

```json
{"action": "run_tests"}
```

```json
{"action": "finish", "summary": "Fixed the boundary condition."}
```

The protocol parser rejects malformed JSON, unknown actions, missing fields,
unexpected fields, absolute paths, and paths escaping the temporary
repository. A protocol error consumes a turn and is returned to the model so
it can recover.

## 4. Repository structure

```text
agent/
  executor.py       confined file, patch, and test actions
  loop.py           iterative agent state machine
  ollama.py         loopback-only Ollama HTTP client
  patches.py        patch validation and final diff generation
  prompt.py         stable system and task prompts
  protocol.py       action types, JSON Schema, and validation
runner/
  benchmark.py      task/model orchestration
  cli.py            local command-line entry point
  config.py         TOML configuration
  manifests.py      task discovery and manifest validation
  storage.py        SQLite schema and persistence
dashboard/
  app.py            Streamlit application
  charts.py         Plotly figure construction
  data.py           SQLite and demo-data queries
tasks/
  <task-id>/
    manifest.json
    instruction.md
    repo/           state visible and editable by the model
    verification/   protected pytest checks, invisible to the model
tests/
  ...               harness, isolation, storage, corpus, and dashboard tests
examples/
  demo_results.jsonl
codepulse.toml
pyproject.toml
README.md
LICENSE
```

The top-level packages follow the requested architecture. Files remain small
and focused so the protocol, execution boundary, persistence, and UI can be
tested independently.

## 5. Task corpus

Every task is a self-contained mini repository with an initial failing state,
a French instruction, and a manifest containing a fixed pytest argument
vector. The model can see only `repo/`; protected verification tests are
copied beside it and included in the fixed test invocation.

The twelve task IDs and intents are:

| Category | Task | Intent |
|---|---|---|
| Fix a bug | `bug_off_by_one` | Correct a range boundary without changing the API |
| Fix a bug | `bug_cache_key` | Stop cache collisions between distinct inputs |
| Add a function | `feature_slugify` | Implement a precisely specified text transformation |
| Add a function | `feature_chunked` | Split a sequence with validated chunk sizes |
| Write a missing test | `test_parse_bool` | Replace a failing test placeholder with assertions for invalid input |
| Write a missing test | `test_safe_divide` | Add the required zero-division behavior test |
| Refactor | `refactor_pricing` | Extract pricing rules while preserving behavior |
| Refactor | `refactor_normalize_record` | Separate normalization steps without regressions |
| CSV | `csv_clean_contacts` | Validate and normalize contact rows |
| CSV | `csv_sales_summary` | Parse sales rows and aggregate valid values |
| Schema/parsing | `parse_config_version` | Reject unsupported or malformed configuration versions |
| Schema/parsing | `parse_event_payload` | Correct event-field validation and type conversion |

Each manifest defines:

- a stable task ID, category, instruction path, and repository path;
- a fixed command equivalent to
  `python -m pytest -q repo/tests verification`;
- a 30-second test timeout;
- UTF-8 text-file and repository-size limits.

The manifest stores the test command as an argument array, never as a shell
string. Corpus validation proves that every initial repository fails and that
the task source is unchanged after a confined execution. The final benchmark
decision is based only on the exit code of a fresh final pytest invocation.

Protected tests reduce trivial benchmark gaming, particularly for
test-writing and refactoring tasks. They are not intended as secret security
boundaries; the corpus is public and synthetic.

## 6. Agent loop and prompt flow

At the beginning of a run, the harness:

1. validates configuration, the selected installed model, and the task;
2. copies `repo/` and protected verification files into a new temporary
   directory;
3. records the initial repository snapshot;
4. sends the instruction, file tree with sizes, action contract, and budget to
   the model;
5. validates and executes one JSON action per turn;
6. appends bounded action results to the conversation;
7. stops on `finish`, the turn limit, a fatal timeout, or cancellation;
8. always runs the fixed final pytest command;
9. computes the final unified diff against the initial snapshot;
10. persists the complete local record before deleting the temporary copy.

`finish` is advisory. It cannot declare success. A run succeeds only when the
fresh final pytest process exits with code zero.

Action outputs are bounded before they return to the model. A single file read
is limited to 64 KiB. Repository tasks remain small enough to fit the common
context budget.

## 7. Security and locality boundary

### Ollama transport

The client uses `http.client`, not environment proxies. Configuration accepts
only plain HTTP with a loopback hostname or address. Host resolution must
produce loopback addresses, redirects are not followed, and the port defaults
to `11434`. The only endpoints used are:

- `GET /api/version`;
- `GET /api/tags`;
- `POST /api/chat`.

There is no code path for `/api/pull`. If Ollama is stopped or a configured
model is missing, the runner fails with a local diagnostic.

### File access

All model-supplied paths are relative, normalized, resolved, and checked
against the temporary editable repository. Symlinks and binary files are
rejected. `list_files` and `read_file` omit the protected verification tree.

### Patch application

`apply_patch` accepts a bounded UTF-8 unified diff. Diff headers are inspected
before execution; absolute paths, parent traversal, paths outside the editable
repository, binary patches, mode changes, submodules, and symlinks are
rejected. The harness invokes a fixed `git apply --check` followed by a fixed
`git apply`, with `shell=False` and patch bytes supplied on standard input.
The model cannot change the executable or its arguments.

### Tests

The only executable action is `run_tests`, which launches the manifest's fixed
pytest argument vector with `shell=False`, the current Python executable, a
sanitized environment, plugin auto-loading disabled, and a hard timeout.
Model content never becomes a command line.

The MVP confines Python-level behavior but is not a hostile-code OS sandbox.
Tasks are project-owned synthetic fixtures. The README states this trust
boundary and warns against importing arbitrary repositories.

## 8. Reproducibility budget

All compared models receive these defaults:

| Parameter | Value |
|---|---:|
| Temperature | `0` |
| Seed | `42` |
| Context window (`num_ctx`) | `8192` tokens |
| Maximum generated tokens per turn (`num_predict`) | `1024` |
| Maximum turns | `12` |
| Ollama response timeout | `120` seconds per turn |
| Test timeout | `30` seconds per invocation |
| Whole-run timeout | `1800` seconds |
| Thinking mode | disabled when supported |

The exact values are configurable but are recorded per run. A comparison batch
uses one immutable configuration snapshot for every model/task pair. The
runner records the exact Ollama tag, model digest, Ollama version, date,
platform, Python version, and parameters.

Temperature zero improves repeatability but does not guarantee byte-identical
generation across Ollama versions, model builds, hardware, or numerical
backends. Results therefore remain tied to the recorded environment.

## 9. Storage

Normal runs use `results/codepulse.sqlite3`. SQLite is configured with foreign
keys and transactions. The schema has two principal tables.

`runs` stores:

- run UUID and `is_demo`;
- model tag, digest, and Ollama version;
- task ID and category;
- serialized parameter snapshot;
- start and finish timestamps;
- terminal status and objective success boolean;
- duration, turn count, and test-run count;
- final patch;
- final pytest exit code, stdout, and stderr;
- error classification and message;
- platform and Python version.

`actions` stores:

- run UUID and turn number;
- action type;
- validated request JSON;
- result JSON;
- start timestamp and duration.

Writes occur incrementally so timeouts and protocol failures remain
inspectable. A run row is finalized transactionally after the mandatory final
test.

`examples/demo_results.jsonl` contains clearly fictional runs with
`is_demo: true`. The dashboard shows a prominent demo badge when that file is
selected. Demo data never appears in normal rankings unless the user
explicitly opens demo mode.

## 10. Command-line interface and configuration

`codepulse.toml` uses only the Python 3.12 standard-library TOML reader. It
selects the loopback Ollama URL, model tags, task IDs, result database, and
common budget.

The supported commands are:

```text
python -m runner.cli list-models
python -m runner.cli validate-tasks
python -m runner.cli run --task bug_off_by_one --model qwen2.5:1.5b
python -m runner.cli batch
python -m runner.cli show-runs
```

`list-models` reads `/api/tags` only. `run` and `batch` refuse any configured
tag absent from that response. This prevents an implicit download.

The initial sample configuration names locally observed tags:
`qwen2.5:1.5b`, `qwen3:1.7b`, and `smollm2:1.7b`. Users edit the list to select
their comparison set.

## 11. Dashboard

The Streamlit application reads a local SQLite path or the packaged demo
JSONL. It contains:

- an overall ranking by success rate, with run counts;
- a Plotly scatter plot of success rate versus median duration by model;
- a model-by-task heatmap using pass, fail, and missing states;
- a run detail view with instruction, metadata, action log, final patch, and
  final pytest output.

Every page displays:

> These results apply only to this corpus, this hardware, this Ollama/model
> build, and these parameters. They are not a general ranking of model
> quality.

The UI loads no remote fonts, scripts, images, analytics, or assets.

## 12. Error handling

Terminal statuses distinguish at least:

- `success`;
- `tests_failed`;
- `protocol_error`;
- `model_timeout`;
- `test_timeout`;
- `ollama_unavailable`;
- `model_missing`;
- `executor_error`;
- `run_timeout`.

Every terminal path records the actions already completed, a final patch, and
the final test evidence when the Python process can be launched. Exceptions
are converted to local records and concise CLI diagnostics; secrets and the
full environment are never persisted.

## 13. Test strategy

Development follows test-first red/green cycles. Critical coverage includes:

- protocol parsing and malformed-action recovery;
- loopback URL enforcement and rejection of redirects/external hosts;
- path traversal, absolute path, symlink, binary, and oversized-read
  rejection;
- allowed patch application and unsafe diff rejection;
- fixed-command execution, timeout handling, and final-test authority;
- temporary-copy isolation and unchanged task sources;
- SQLite round trips and interrupted-run preservation;
- aggregation for ranking, scatter, heatmap, and detail views;
- all twelve manifests and initially failing corpus states;
- a scripted fake-model end-to-end run;
- one real end-to-end run against an already installed Ollama model.

The full real-model run uses `qwen3:8b` on one small task unless hardware
constraints make `qwen2.5:1.5b` the viable installed alternative. The outcome
is recorded as observed; no result is fabricated or changed to make the demo
look successful.

## 14. Python and dependency constraint

The source targets Python 3.12 and avoids newer syntax. The machine currently
has Python 3.12.10 but lacks cached Python 3.12 wheels for pytest, Streamlit,
Plotly, and their compiled dashboard dependencies. Network installation is
forbidden.

Accordingly:

- core compatibility checks run with the installed Python 3.12 interpreter;
- the full pytest and dashboard smoke checks may use the already installed,
  entirely local Conda Python 3.13 environment;
- this verification exception is reported explicitly;
- normal installation documentation requires Python 3.12 dependencies from a
  user-provided local wheelhouse or an already provisioned environment and
  never instructs the project to fetch them automatically.

## 15. Licensing and documentation

Project code, task repositories, task tests, prompts, and documentation use the
MIT license in `LICENSE`. `pyproject.toml` declares MIT for this project only.

The repository contains no model files, GGUF files, blobs, or weights. The
README states that Ollama models and third-party Python dependencies retain
their own licenses and that users must review them separately, for example
with local Ollama model metadata.

## 16. Known limitations

- Twelve synthetic tasks are a small corpus and can overfit model behavior.
- Public protected tests discourage trivial edits but are not secret.
- Runtime depends on hardware, quantization, Ollama, and warm/cold model state.
- Temperature zero does not make all inference deterministic.
- `git apply` is a fixed local dependency of patch execution.
- The executor is designed for trusted synthetic tasks, not hostile code.
- The current machine cannot fully validate the dashboard under Python 3.12
  without a local compatible dependency set.
- Ollama Desktop may perform its own update check when launched. Reproduction
  should start the server process directly with `ollama serve`, keep the
  desktop updater disabled, and confirm the local API before running the
  benchmark.

These limitations are displayed in the README and the dashboard rather than
being generalized away in reported results.
