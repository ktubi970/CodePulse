# CodePulse Local

A reproducible, visual, local benchmark for small language models (SLMs) acting as coding agents through an offline [Ollama](https://ollama.com) server.

> **Disclaimer:** These benchmark results apply only to this task corpus, this hardware, this Ollama/model build, and these budget parameters. They do not constitute a general ranking of overall model quality.

---

## 🎯 Purpose and Scope

CodePulse Local answers a specific question:
> *Under identical constraints, which locally hosted models solve small Python programming tasks most effectively?*

Key characteristics:
- **100% Offline & Local**: Talks exclusively to Ollama at `http://127.0.0.1:11434`. Never pulls models automatically, calls external APIs, or publishes data.
- **Model-Independent JSON Protocol**: Uses a 6-action JSON protocol over `/api/chat` without requiring native function calling.
- **Checked Verification**: Success requires a fresh, isolated `pytest` run on hidden verification checks with exit code zero *and* a clean JUnit report; test-writing tasks must also catch known mutants. Every task ships a reference solution that the test suite proves solvable.
- **Visual Analytics**: Interactive Streamlit dashboard with Plotly charts (rankings, duration vs success scatter plot, pass/fail heatmap, and step-by-step run logs).

---

## ⚙️ Architecture and Action Protocol

One model response produces exactly one action JSON object per turn:

```json
{"action": "list_files"}
{"action": "read_file", "path": "src/example.py"}
{"action": "write_file", "path": "src/example.py", "content": "def add(a, b):\n    return a + b\n"}
{"action": "apply_patch", "patch": "--- a/src/example.py\n+++ b/src/example.py\n@@ ..."}
{"action": "run_tests"}
{"action": "finish", "summary": "Fixed boundary condition."}
```

`write_file` replaces a whole file and is the recommended way to edit: in a first batch of
runs, small models (0.5B–3B) produced 352 unified diffs and `git apply` accepted none of them.
`apply_patch` remains available for models that can emit exact diffs.

```text
agent/
  executor.py       confined file, patch, and test actions
  loop.py           iterative agent state machine
  ollama.py         loopback-only Ollama HTTP client
  patches.py        patch header validation and diff generation
  prompt.py         system and task prompts
  protocol.py       action parser and JSON schema
runner/
  benchmark.py      task/model orchestration
  cli.py            command-line interface
  config.py         TOML configuration loader
  manifests.py      task discovery and manifest validation
  storage.py        SQLite persistence
dashboard/
  app.py            Streamlit web dashboard
  charts.py         Plotly chart generators
  data.py           SQLite and demo data loaders
tasks/
  <task-id>/        12 synthetic Python coding tasks (repo, hidden checks, reference solution)
examples/
  demo_results.jsonl Fictional dataset for demo UI mode
```

---

## 🚀 Installation & Setup

### Requirements
- **Python 3.12+**
- **Git** (for patch application via `git apply`)
- **Ollama** server running locally (`http://127.0.0.1:11434`)

### Local Installation

Use a virtual environment. Tests run in isolated mode (`python -I`), which ignores user
site-packages: a pytest installed with `pip install --user` is invisible to the harness.
The CLI checks this before running and stops with an explicit error.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .[test]
```

Or using an offline local wheelhouse:

```powershell
py -3.12 -m pip install --no-index --find-links D:\wheelhouse -e .[test]
```

---

## 💻 Command-Line Interface (CLI)

### 1. List Locally Installed Models
Inspect local Ollama models (`GET /api/tags`):

```powershell
python -m runner.cli list-models
```

### 2. Validate Tasks & Initial Baselines
Check that the test runtime works, that every task's initial state fails, and that every
reference solution passes (and catches the task's mutants). Exits non-zero on any problem:

```powershell
python -m runner.cli validate-tasks
```

### 3. Run a Single Benchmark Task
Run a specific model against a single task:

```powershell
python -m runner.cli run --model qwen2.5:1.5b --task bug_off_by_one
```

### 4. Run Complete Benchmark Matrix
Run all configured model and task combinations specified in `codepulse.toml`:

```powershell
python -m runner.cli batch
```

### 5. View Stored Benchmark Runs
Inspect recorded runs from the local SQLite database:

```powershell
python -m runner.cli show-runs --limit 20
```

---

## 📊 Interactive Web Dashboard

Launch the local Streamlit dashboard to visualize results:

```powershell
python -m streamlit run dashboard/app.py
```

### Demo Mode
To preview the dashboard with fictional demo data without running a benchmark:

```powershell
$env:CODEPULSE_DEMO='1'
python -m streamlit run dashboard/app.py
```

---

## 🛡️ Security & Trust Boundary

- **No Remote Calls**: The harness rejects non-loopback HTTP endpoints and contains no code paths for `/api/pull`, telemetry, or remote uploads.
- **Confined File Actions**: `read_file`, `write_file` and `apply_patch` operate on a temporary copy of the task repository. Paths escaping it or containing `..` parent traversal are rejected.
- **No Arbitrary Shell**: `run_tests` launches fixed `pytest` command vectors with sanitized environment variables; model output never becomes a command line.
- **Hardened Verification**: pytest runs with `python -I -B`, `--noconftest` and `-p no:cacheprovider`, and success requires a clean JUnit report. This blocks the bypasses covered by `tests/test_verification_integrity.py` (`sitecustomize.py`, `conftest.py` hooks, `os._exit(0)`, skipped tests).
- **Not a Sandbox**: the code the model writes is executed by pytest with your user privileges. The checks above stop accidental and trivial bypasses, not a deliberately malicious model (for example one that loads a pytest plugin from its own test files). Run untrusted models inside a container or VM.

---

## 📄 License

Project source code, task repositories, test suites, and documentation are licensed under the [MIT License](LICENSE).
Ollama model weights retain their respective open weights licenses.
