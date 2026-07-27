# CodePulse Local Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reproducible, visual, entirely local benchmark that compares installed Ollama models as constrained coding agents on twelve synthetic Python tasks.

**Architecture:** A model-independent JSON action loop talks only to a validated loopback Ollama API. A confined executor operates on a temporary repository copy, a runner records authoritative final pytest evidence in SQLite, and a local Streamlit/Plotly dashboard visualizes normal or explicitly marked demo runs.

**Tech Stack:** Python 3.12-compatible source, standard-library `http.client`, `sqlite3`, `tomllib`, and `dataclasses`; pytest; Streamlit; Plotly; local Git; Ollama at `http://127.0.0.1:11434`.

## Global Constraints

- Runtime model traffic must remain local and use Ollama at `http://localhost:11434` or its loopback-equivalent `http://127.0.0.1:11434`.
- Never download a model; configured tags absent from `GET /api/tags` must fail closed.
- Never send code, prompts, data, actions, patches, or results to an external service.
- Project code, task corpus, prompts, tests, and documentation use the MIT license.
- Model weights are neither included nor redistributed; their licenses remain distinct.
- Never publish to GitHub or contact another external service.
- Source targets Python 3.12 and uses no syntax introduced after Python 3.12.
- Every benchmark success is determined only by a fresh final fixed pytest invocation with exit code zero.
- Model actions are limited to list files, read a file, apply a patch, run the fixed task tests, and finish.
- The model never receives arbitrary shell access and never controls an executable or command argument.
- Default common budget: temperature `0`, seed `42`, `num_ctx=8192`, `num_predict=1024`, `max_turns=12`, response timeout `120s`, test timeout `30s`, whole-run timeout `1800s`.
- The current machine may use local Conda Python 3.13 for pytest and dashboard smoke verification; Python 3.12 compatibility receives a separate compile/import check and the exception is documented.
- No dependency installation command may access a network. Use only already installed local packages.

---

## File map

| Path | Responsibility |
|---|---|
| `pyproject.toml` | Python floor, dependency metadata, pytest settings, CLI entry point |
| `codepulse.toml` | Loopback endpoint, model selection, tasks, result path, common budget |
| `agent/protocol.py` | Strict action dataclasses, schema, parsing, validation |
| `agent/ollama.py` | No-proxy/no-redirect loopback HTTP transport and model metadata |
| `agent/patches.py` | Safe diff header validation, snapshots, final unified diff |
| `agent/executor.py` | Confined file actions, fixed patch command, fixed pytest command |
| `agent/prompt.py` | Stable system/task messages and bounded observations |
| `agent/loop.py` | Iterative action state machine and mandatory final test |
| `runner/config.py` | Typed TOML configuration and budget validation |
| `runner/manifests.py` | Task manifest discovery and trusted fixed-command validation |
| `runner/storage.py` | SQLite schema, run/action writes, finalization |
| `runner/benchmark.py` | Task/model orchestration and immutable batch configuration |
| `runner/cli.py` | `list-models`, `validate-tasks`, `run`, `batch`, `show-runs` |
| `dashboard/data.py` | SQLite/demo loading and aggregate view models |
| `dashboard/charts.py` | Ranking, scatter, and heatmap Plotly figures |
| `dashboard/app.py` | Streamlit pages, demo badge, disclaimer, run detail |
| `tasks/*` | Twelve initial repositories, instructions, manifests, protected checks |
| `examples/demo_results.jsonl` | Clearly fictional dashboard dataset |
| `tests/*` | Unit, integration, corpus, storage, dashboard, and scripted E2E checks |
| `README.md` | Offline setup, usage, architecture, reproducibility, trust boundary, limits |
| `LICENSE` | MIT license text for project-owned artifacts |

---

### Task 1: Project foundation and typed configuration

**Files:**
- Create: `pyproject.toml`
- Create: `codepulse.toml`
- Create: `agent/__init__.py`
- Create: `runner/__init__.py`
- Create: `dashboard/__init__.py`
- Create: `tests/__init__.py`
- Create: `runner/config.py`
- Create: `tests/test_config.py`

**Interfaces:**
- Consumes: Python 3.12 `tomllib`.
- Produces: `OllamaConfig`, `BudgetConfig`, `AppConfig`, and `load_config(path: Path) -> AppConfig`.

- [ ] **Step 1: Write the failing configuration tests**

```python
from pathlib import Path

import pytest

from runner.config import ConfigError, load_config


def test_load_config_returns_fixed_common_budget(tmp_path: Path) -> None:
    path = tmp_path / "codepulse.toml"
    path.write_text(
        """
[ollama]
base_url = "http://127.0.0.1:11434"

[benchmark]
models = ["qwen2.5:1.5b"]
tasks = ["bug_off_by_one"]
result_db = "results/test.sqlite3"
temperature = 0.0
seed = 42
context_tokens = 8192
max_output_tokens = 1024
max_turns = 12
response_timeout_s = 120.0
test_timeout_s = 30.0
run_timeout_s = 1800.0
""",
        encoding="utf-8",
    )

    config = load_config(path)

    assert config.ollama.base_url == "http://127.0.0.1:11434"
    assert config.models == ("qwen2.5:1.5b",)
    assert config.budget.max_turns == 12
    assert config.result_db == (tmp_path / "results/test.sqlite3").resolve()


def test_load_config_rejects_non_loopback_endpoint(tmp_path: Path) -> None:
    path = tmp_path / "codepulse.toml"
    path.write_text(
        '[ollama]\nbase_url="https://example.com"\n'
        '[benchmark]\nmodels=["m"]\ntasks=["t"]\nresult_db="r.db"\n',
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="loopback"):
        load_config(path)
```

- [ ] **Step 2: Run the tests and verify the missing-module failure**

Run:

```powershell
C:\Users\ktubi\anaconda3\python.exe -m pytest tests/test_config.py -q
```

Expected: collection fails because `runner.config` does not exist.

- [ ] **Step 3: Implement immutable configuration types and validation**

```python
from dataclasses import dataclass
from pathlib import Path
import ipaddress
import socket
import tomllib
from urllib.parse import urlsplit


class ConfigError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class OllamaConfig:
    base_url: str


@dataclass(frozen=True, slots=True)
class BudgetConfig:
    temperature: float = 0.0
    seed: int = 42
    context_tokens: int = 8192
    max_output_tokens: int = 1024
    max_turns: int = 12
    response_timeout_s: float = 120.0
    test_timeout_s: float = 30.0
    run_timeout_s: float = 1800.0


@dataclass(frozen=True, slots=True)
class AppConfig:
    ollama: OllamaConfig
    models: tuple[str, ...]
    tasks: tuple[str, ...]
    result_db: Path
    budget: BudgetConfig


def require_loopback_http(url: str) -> None:
    parts = urlsplit(url)
    if parts.scheme != "http" or parts.hostname is None:
        raise ConfigError("Ollama URL must use plain HTTP on loopback")
    addresses = socket.getaddrinfo(parts.hostname, parts.port or 80)
    if not addresses or any(
        not ipaddress.ip_address(item[4][0]).is_loopback for item in addresses
    ):
        raise ConfigError("Ollama URL must resolve only to loopback")
```

Implement `load_config` by reading the named sections, rejecting an empty
model list and non-positive numeric budgets, allowing an empty task list to
mean all discovered tasks, and resolving `result_db` relative to the TOML
file.

- [ ] **Step 4: Add project metadata and the checked-in default config**

`pyproject.toml` must declare `requires-python = ">=3.12,<3.15"`, MIT project
license metadata, runtime dependencies `streamlit>=1.40` and `plotly>=5.24`,
the optional `test` dependency `pytest>=8`, and the entry point
`codepulse = "runner.cli:main"`. Configure pytest with
`testpaths = ["tests"]` and `addopts = "-ra"`.

`codepulse.toml` must name only already observed local tags:

```toml
[ollama]
base_url = "http://127.0.0.1:11434"

[benchmark]
models = ["qwen2.5:1.5b", "qwen3:1.7b", "smollm2:1.7b"]
tasks = []
result_db = "results/codepulse.sqlite3"
temperature = 0.0
seed = 42
context_tokens = 8192
max_output_tokens = 1024
max_turns = 12
response_timeout_s = 120.0
test_timeout_s = 30.0
run_timeout_s = 1800.0
```

Treat an empty task list as “all discovered tasks”, while an empty model list
remains invalid.

- [ ] **Step 5: Run the configuration tests and Python 3.12 compilation**

```powershell
C:\Users\ktubi\anaconda3\python.exe -m pytest tests/test_config.py -q
py -3.12 -m compileall -q agent runner dashboard
```

Expected: tests pass and compileall exits zero.

- [ ] **Step 6: Commit the foundation**

```powershell
git add pyproject.toml codepulse.toml agent runner dashboard tests/__init__.py tests/test_config.py
git commit -m "feat: add offline benchmark configuration"
```

---

### Task 2: Strict JSON action protocol

**Files:**
- Create: `agent/protocol.py`
- Create: `tests/test_protocol.py`

**Interfaces:**
- Consumes: JSON response text from any Ollama model.
- Produces: `ListFiles`, `ReadFile`, `ApplyPatch`, `RunTests`, `Finish`,
  `Action`, `ProtocolError`, `parse_action(raw: str) -> Action`, and
  `action_json_schema() -> dict[str, object]`.

- [ ] **Step 1: Write failing tests for valid and invalid actions**

```python
import json

import pytest

from agent.protocol import (
    ApplyPatch,
    ProtocolError,
    ReadFile,
    action_json_schema,
    parse_action,
)


def test_parse_read_file_action() -> None:
    assert parse_action('{"action":"read_file","path":"src/calc.py"}') == ReadFile(
        path="src/calc.py"
    )


def test_parse_patch_preserves_unified_diff() -> None:
    patch = "--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-x = 1\n+x = 2\n"
    action = parse_action(json.dumps({"action": "apply_patch", "patch": patch}))
    assert action == ApplyPatch(patch=patch)


@pytest.mark.parametrize(
    "raw,message",
    [
        ("not-json", "valid JSON"),
        ('{"action":"shell","command":"dir"}', "unknown action"),
        ('{"action":"read_file","path":"../secret"}', "relative"),
        ('{"action":"run_tests","extra":1}', "unexpected"),
    ],
)
def test_parse_action_fails_closed(raw: str, message: str) -> None:
    with pytest.raises(ProtocolError, match=message):
        parse_action(raw)


def test_schema_exposes_only_five_actions() -> None:
    schema = action_json_schema()
    assert schema["properties"]["action"]["enum"] == [
        "list_files",
        "read_file",
        "apply_patch",
        "run_tests",
        "finish",
    ]
```

- [ ] **Step 2: Verify the tests fail because the protocol is absent**

```powershell
C:\Users\ktubi\anaconda3\python.exe -m pytest tests/test_protocol.py -q
```

Expected: import failure for `agent.protocol`.

- [ ] **Step 3: Implement frozen action dataclasses and strict parsing**

```python
from dataclasses import dataclass
import json
from pathlib import PurePosixPath
from typing import TypeAlias


class ProtocolError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ListFiles:
    action: str = "list_files"


@dataclass(frozen=True, slots=True)
class ReadFile:
    path: str
    action: str = "read_file"


@dataclass(frozen=True, slots=True)
class ApplyPatch:
    patch: str
    action: str = "apply_patch"


@dataclass(frozen=True, slots=True)
class RunTests:
    action: str = "run_tests"


@dataclass(frozen=True, slots=True)
class Finish:
    summary: str
    action: str = "finish"


Action: TypeAlias = ListFiles | ReadFile | ApplyPatch | RunTests | Finish


def _relative_path(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ProtocolError("path must be a non-empty relative path")
    path = PurePosixPath(value.replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts:
        raise ProtocolError("path must be relative and cannot traverse parents")
    return path.as_posix()
```

`parse_action` must decode one JSON object, compare its exact key set with the
selected action contract, validate a 256 KiB response ceiling, require a
non-empty bounded patch or summary where applicable, and return the matching
dataclass.

- [ ] **Step 4: Implement a conservative Ollama JSON Schema**

Return a schema with an `action` enum and optional `path`, `patch`, and
`summary` string properties, `additionalProperties: false`, and `action`
required. Action-specific validation remains in `parse_action`, avoiding
JSON-Schema features unsupported by smaller models.

- [ ] **Step 5: Run protocol tests and compile under Python 3.12**

```powershell
C:\Users\ktubi\anaconda3\python.exe -m pytest tests/test_protocol.py -q
py -3.12 -m compileall -q agent/protocol.py
```

Expected: all protocol tests pass and compileall exits zero.

- [ ] **Step 6: Commit**

```powershell
git add agent/protocol.py tests/test_protocol.py
git commit -m "feat: define constrained agent protocol"
```

---

### Task 3: Loopback-only Ollama client

**Files:**
- Create: `agent/ollama.py`
- Create: `tests/test_ollama.py`

**Interfaces:**
- Consumes: validated local Ollama base URL and chat messages.
- Produces: `OllamaClient`, `OllamaModel`, `OllamaReply`,
  `OllamaUnavailable`, `ModelMissing`.

- [ ] **Step 1: Write failing tests using a real loopback HTTP server**

```python
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from threading import Thread

import pytest

from agent.ollama import ModelMissing, OllamaClient
from runner.config import ConfigError


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        payload = {
            "/api/version": {"version": "0.test"},
            "/api/tags": {
                "models": [
                    {
                        "name": "local:test",
                        "digest": "abc",
                        "details": {"parameter_size": "1B", "quantization_level": "Q4"},
                    }
                ]
            },
        }[self.path]
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


@pytest.fixture
def server_url() -> Iterator[str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_client_reads_version_and_tags_from_loopback(server_url: str) -> None:
    client = OllamaClient(server_url, timeout_seconds=1)
    assert client.version() == "0.test"
    assert client.list_models()[0].name == "local:test"


def test_client_rejects_external_url() -> None:
    with pytest.raises(ConfigError, match="loopback"):
        OllamaClient("http://example.com:11434")


def test_require_model_never_pulls_missing_tag(server_url: str) -> None:
    client = OllamaClient(server_url, timeout_seconds=1)
    with pytest.raises(ModelMissing, match="missing:test"):
        client.require_model("missing:test")
```

Import `Iterator` from `collections.abc` for the fixture return annotation.

- [ ] **Step 2: Run and observe the missing-client failure**

```powershell
C:\Users\ktubi\anaconda3\python.exe -m pytest tests/test_ollama.py -q
```

Expected: import failure for `agent.ollama`.

- [ ] **Step 3: Implement direct `http.client` transport**

```python
from dataclasses import dataclass
import http.client
import json
from typing import Any
from urllib.parse import urlsplit

from runner.config import require_loopback_http


@dataclass(frozen=True, slots=True)
class OllamaModel:
    name: str
    digest: str
    parameter_size: str
    quantization: str


@dataclass(frozen=True, slots=True)
class OllamaReply:
    content: str
    prompt_tokens: int
    completion_tokens: int
    total_duration_ns: int


class OllamaUnavailable(RuntimeError):
    pass


class ModelMissing(RuntimeError):
    pass


class OllamaClient:
    def __init__(self, base_url: str, timeout_seconds: float) -> None:
        require_loopback_http(base_url)
        parts = urlsplit(base_url)
        self._host = parts.hostname or "127.0.0.1"
        self._port = parts.port or 11434
        self._timeout = timeout_seconds
```

Implement a private `_request` that opens a new `HTTPConnection` for every
call, sends JSON bytes directly, caps responses at 4 MiB, rejects non-JSON,
and maps connection/timeout failures to `OllamaUnavailable`. Do not implement
redirect handling or a pull endpoint.

- [ ] **Step 4: Implement chat payload and missing-model preflight**

`chat` sends:

```python
payload = {
    "model": model,
    "messages": messages,
    "stream": False,
    "format": response_schema,
    "think": False,
    "options": {
        "temperature": temperature,
        "seed": seed,
        "num_ctx": context_tokens,
        "num_predict": max_output_tokens,
    },
}
```

It parses `message.content`, `prompt_eval_count`, `eval_count`, and
`total_duration`. `require_model` compares exact tags from `list_models` and
raises `ModelMissing`; it never attempts remediation.

- [ ] **Step 5: Run client tests and the external-host mutation check**

```powershell
C:\Users\ktubi\anaconda3\python.exe -m pytest tests/test_ollama.py -q
py -3.12 -m compileall -q agent/ollama.py
```

Expected: loopback tests pass; changing the host validation to accept
`example.com` makes `test_client_rejects_external_url` fail.

- [ ] **Step 6: Commit**

```powershell
git add agent/ollama.py tests/test_ollama.py
git commit -m "feat: add loopback-only Ollama client"
```

---

### Task 4: Task manifests and corpus discovery

**Files:**
- Create: `runner/manifests.py`
- Create: `tests/test_manifests.py`
- Create: `tasks/.gitkeep`

**Interfaces:**
- Consumes: `tasks/<id>/manifest.json` and task directory paths.
- Produces: `TaskManifest`, `ManifestError`,
  `load_manifest(task_dir: Path) -> TaskManifest`,
  `discover_tasks(root: Path) -> dict[str, TaskManifest]`.

- [ ] **Step 1: Write failing manifest tests**

```python
import json
from pathlib import Path

import pytest

from runner.manifests import ManifestError, discover_tasks, load_manifest


def write_task(root: Path, task_id: str = "sample") -> Path:
    task = root / task_id
    (task / "repo").mkdir(parents=True)
    (task / "verification").mkdir()
    (task / "instruction.md").write_text("Fix it.\n", encoding="utf-8")
    (task / "manifest.json").write_text(
        json.dumps(
            {
                "id": task_id,
                "category": "fix_bug",
                "instruction": "instruction.md",
                "repo": "repo",
                "verification": "verification",
                "test_argv": [
                    "{python}",
                    "-m",
                    "pytest",
                    "-q",
                    "repo/tests",
                    "verification",
                ],
                "test_timeout_s": 30.0,
            }
        ),
        encoding="utf-8",
    )
    return task


def test_load_manifest_accepts_only_fixed_pytest_vector(tmp_path: Path) -> None:
    manifest = load_manifest(write_task(tmp_path))
    assert manifest.task_id == "sample"
    assert manifest.test_argv[:4] == ("{python}", "-m", "pytest", "-q")


def test_manifest_rejects_shell_command_string(tmp_path: Path) -> None:
    task = write_task(tmp_path)
    data = json.loads((task / "manifest.json").read_text(encoding="utf-8"))
    data["test_argv"] = "pytest -q && curl example.com"
    (task / "manifest.json").write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ManifestError, match="argument array"):
        load_manifest(task)


def test_discovery_rejects_duplicate_manifest_id(tmp_path: Path) -> None:
    write_task(tmp_path, "one")
    second = write_task(tmp_path, "two")
    data = json.loads((second / "manifest.json").read_text(encoding="utf-8"))
    data["id"] = "one"
    (second / "manifest.json").write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ManifestError, match="duplicate"):
        discover_tasks(tmp_path)
```

- [ ] **Step 2: Verify the missing implementation failure**

```powershell
C:\Users\ktubi\anaconda3\python.exe -m pytest tests/test_manifests.py -q
```

Expected: import failure for `runner.manifests`.

- [ ] **Step 3: Implement the immutable manifest**

```python
@dataclass(frozen=True, slots=True)
class TaskManifest:
    task_id: str
    category: str
    task_dir: Path
    instruction_path: Path
    repo_path: Path
    verification_path: Path
    test_argv: tuple[str, ...]
    test_timeout_s: float

    def instruction(self) -> str:
        return self.instruction_path.read_text(encoding="utf-8")
```

Validate identifiers against `[a-z][a-z0-9_]{2,63}`, require the exact
`("{python}", "-m", "pytest")` prefix, allow only known pytest flags and the
two relative test roots, reject absolute paths and parent traversal, require
all declared paths to resolve inside the task directory, and reject symlinks.

- [ ] **Step 4: Run manifest tests**

```powershell
C:\Users\ktubi\anaconda3\python.exe -m pytest tests/test_manifests.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add runner/manifests.py tests/test_manifests.py tasks/.gitkeep
git commit -m "feat: validate benchmark task manifests"
```

---

### Task 5: Safe patches and repository snapshots

**Files:**
- Create: `agent/patches.py`
- Create: `tests/test_patches.py`

**Interfaces:**
- Consumes: editable repository root and UTF-8 unified diff.
- Produces: `PatchError`, `snapshot_tree(root: Path) -> dict[str, bytes]`,
  `validate_patch(patch: str, max_bytes: int = 262144) -> tuple[str, ...]`,
  `apply_patch(root: Path, patch: str) -> tuple[str, ...]`,
  `build_final_diff(before: Mapping[str, bytes], after: Mapping[str, bytes]) -> str`.

- [ ] **Step 1: Write failing patch safety tests**

```python
from pathlib import Path

import pytest

from agent.patches import PatchError, apply_patch, build_final_diff, snapshot_tree


def test_apply_patch_changes_only_declared_relative_file(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("value = 1\n", encoding="utf-8")
    changed = apply_patch(
        tmp_path,
        "--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-value = 1\n+value = 2\n",
    )
    assert changed == ("a.py",)
    assert (tmp_path / "a.py").read_text(encoding="utf-8") == "value = 2\n"


@pytest.mark.parametrize(
    "header",
    [
        "--- a/a.py\n+++ b/../outside.py\n",
        "--- C:/secret.py\n+++ C:/secret.py\n",
        "--- /dev/null\n+++ b/link.py\nnew file mode 120000\n",
        "GIT binary patch\n",
    ],
)
def test_apply_patch_rejects_unsafe_headers(tmp_path: Path, header: str) -> None:
    with pytest.raises(PatchError):
        apply_patch(tmp_path, header)


def test_final_diff_includes_created_and_deleted_text_files(tmp_path: Path) -> None:
    (tmp_path / "old.py").write_text("old\n", encoding="utf-8")
    before = snapshot_tree(tmp_path)
    (tmp_path / "old.py").unlink()
    (tmp_path / "new.py").write_text("new\n", encoding="utf-8")
    diff = build_final_diff(before, snapshot_tree(tmp_path))
    assert "--- a/old.py" in diff
    assert "+++ b/new.py" in diff
```

- [ ] **Step 2: Run and observe the missing-module failure**

```powershell
C:\Users\ktubi\anaconda3\python.exe -m pytest tests/test_patches.py -q
```

- [ ] **Step 3: Implement header validation and fixed Git invocation**

Parse `---`/`+++` paths, normalize `a/` and `b/` prefixes, allow `/dev/null`
only for creation/deletion, and reject these exact markers:

```python
FORBIDDEN_MARKERS = (
    "GIT binary patch",
    "Binary files ",
    "new file mode 120000",
    "old mode ",
    "new mode ",
    "Subproject commit ",
)
```

After validation, invoke:

```python
check = subprocess.run(
    ["git", "apply", "--check", "--whitespace=nowarn", "-"],
    cwd=root,
    input=patch.encode("utf-8"),
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    shell=False,
    timeout=10,
    check=False,
)
```

Run the identical command without `--check` only if the check exits zero.
Before and after execution, reject any symlink under `root`. Confirm every
changed snapshot path was named by the validated patch.

- [ ] **Step 4: Implement deterministic snapshots and final diffs**

Snapshots recursively sort relative POSIX paths, skip `__pycache__`,
`.pytest_cache`, and `.git`, reject files over 1 MiB and binary NUL bytes, and
store raw bytes. `build_final_diff` decodes UTF-8 and uses
`difflib.unified_diff` with `a/<path>` and `b/<path>` labels.

- [ ] **Step 5: Run patch tests**

```powershell
C:\Users\ktubi\anaconda3\python.exe -m pytest tests/test_patches.py -q
```

Expected: safe patch passes; all unsafe variants fail before Git changes a
file.

- [ ] **Step 6: Commit**

```powershell
git add agent/patches.py tests/test_patches.py
git commit -m "feat: confine unified patch application"
```

---

### Task 6: Confined workspace executor and isolation

**Files:**
- Create: `agent/executor.py`
- Create: `tests/test_executor.py`
- Create: `tests/test_isolation.py`

**Interfaces:**
- Consumes: `TaskManifest` and one validated `Action`.
- Produces: `ActionResult`, `TestResult`, `WorkspaceExecutor`,
  `WorkspaceExecutor.create(manifest, test_timeout_s)`,
  `execute(action: Action) -> ActionResult`, `final_test() -> TestResult`,
  `final_diff() -> str`, and context-manager cleanup.

- [ ] **Step 1: Write failing confinement tests**

```python
from pathlib import Path

import pytest

from agent.executor import ExecutorError, WorkspaceExecutor
from agent.protocol import ReadFile, RunTests
from tests.test_manifests import write_task
from runner.manifests import load_manifest


def test_read_file_cannot_escape_editable_copy(tmp_path: Path) -> None:
    task = write_task(tmp_path)
    (task / "repo" / "safe.py").write_text("safe = True\n", encoding="utf-8")
    manifest = load_manifest(task)
    with WorkspaceExecutor.create(manifest, test_timeout_s=1) as executor:
        with pytest.raises(ExecutorError, match="outside"):
            executor.read_file("../verification/test_hidden.py")


def test_test_action_uses_manifest_vector_not_model_text(tmp_path: Path) -> None:
    task = write_task(tmp_path)
    tests = task / "repo" / "tests"
    tests.mkdir()
    (tests / "test_ok.py").write_text("def test_ok(): assert True\n", encoding="utf-8")
    manifest = load_manifest(task)
    with WorkspaceExecutor.create(manifest, test_timeout_s=5) as executor:
        result = executor.execute(RunTests())
    assert result.kind == "test_result"
    assert result.data["exit_code"] == 0


def test_original_repository_remains_unchanged(tmp_path: Path) -> None:
    task = write_task(tmp_path)
    source = task / "repo" / "value.py"
    source.write_text("value = 1\n", encoding="utf-8")
    manifest = load_manifest(task)
    with WorkspaceExecutor.create(manifest, test_timeout_s=1) as executor:
        executor.repo_root.joinpath("value.py").write_text("value = 2\n", encoding="utf-8")
    assert source.read_text(encoding="utf-8") == "value = 1\n"
```

- [ ] **Step 2: Verify missing-executor failures**

```powershell
C:\Users\ktubi\anaconda3\python.exe -m pytest tests/test_executor.py tests/test_isolation.py -q
```

- [ ] **Step 3: Implement temporary layout and path guards**

`create` makes:

```text
<temp>/
  repo/           copied editable repository
  verification/   copied protected tests
```

Record `snapshot_tree(repo)` before any action. Resolve model paths against
`repo`, require `candidate.is_relative_to(repo.resolve())`, reject symlinks,
limit reads to 64 KiB, and render file listings as sorted
`"<path>\t<size> bytes"` lines.

- [ ] **Step 4: Implement fixed pytest execution**

Replace only `{python}` with `sys.executable`; keep every other manifest
argument unchanged. Run from the temporary root with `shell=False`, capture
UTF-8 output with replacement, cap each stream at 256 KiB, and use this
allowlisted environment:

```python
env = {
    key: os.environ[key]
    for key in ("PATH", "SYSTEMROOT", "TEMP", "TMP", "PATHEXT", "COMSPEC")
    if key in os.environ
}
env.update(
    {
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        "NO_PROXY": "*",
        "no_proxy": "*",
    }
)
```

Map timeout to a `TestResult` with `timed_out=True`, `exit_code=None`, and
captured partial output. Count every test invocation.

- [ ] **Step 5: Dispatch only the five action dataclasses**

`ListFiles` returns a listing, `ReadFile` returns content, `ApplyPatch` calls
the safe patch module, `RunTests` calls the fixed runner, and `Finish` returns
its summary without changing success. Any other object raises `ExecutorError`.

- [ ] **Step 6: Run executor and isolation tests**

```powershell
C:\Users\ktubi\anaconda3\python.exe -m pytest tests/test_executor.py tests/test_isolation.py -q
```

Expected: path confinement, command authority, timeout, and source isolation
tests pass.

- [ ] **Step 7: Commit**

```powershell
git add agent/executor.py tests/test_executor.py tests/test_isolation.py
git commit -m "feat: isolate repository actions and tests"
```

---

### Task 7: SQLite result storage

**Files:**
- Create: `runner/storage.py`
- Create: `tests/test_storage.py`

**Interfaces:**
- Consumes: run metadata, action observations, terminal evidence.
- Produces: `RunRecord`, `ActionRecord`, `ResultStore`,
  `start_run(record)`, `append_action(record)`, `finish_run(...)`,
  `get_run(run_id)`, and `list_runs()`.

- [ ] **Step 1: Write failing round-trip and interrupted-run tests**

```python
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

    assert loaded["success"] == 1
    assert loaded["final_test_exit_code"] == 0
    assert loaded["actions"][0]["action_type"] == "read_file"


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
    assert store.get_run(run.run_id)["status"] == "running"
```

- [ ] **Step 2: Verify missing-storage failures**

```powershell
C:\Users\ktubi\anaconda3\python.exe -m pytest tests/test_storage.py -q
```

- [ ] **Step 3: Implement schema initialization**

Create `runs` and `actions` using the exact columns from the approved design.
Enable `PRAGMA foreign_keys=ON` for every connection. Use
`sqlite3.Row`, ISO-8601 UTC timestamps, UUID4 run IDs, JSON with sorted keys,
and one transaction per public method. Add indexes on model, task, status,
and action run/turn.

- [ ] **Step 4: Implement typed record factories and persistence**

`RunRecord.new` captures `platform.platform()` and `platform.python_version()`.
`finish_run` updates only a row whose current status is `running`, and raises
`StorageError` if no row changes. `append_action` uses a unique
`(run_id, turn)` key so duplicate turns fail visibly.

- [ ] **Step 5: Run storage tests**

```powershell
C:\Users\ktubi\anaconda3\python.exe -m pytest tests/test_storage.py -q
```

Expected: final and interrupted records round-trip exactly.

- [ ] **Step 6: Commit**

```powershell
git add runner/storage.py tests/test_storage.py
git commit -m "feat: persist benchmark evidence in SQLite"
```

---

### Task 8: Stable prompt and iterative agent loop

**Files:**
- Create: `agent/prompt.py`
- Create: `agent/loop.py`
- Create: `tests/test_agent_loop.py`

**Interfaces:**
- Consumes: `OllamaClient`, `OllamaModel`, `TaskManifest`,
  `WorkspaceExecutor`, `BudgetConfig`, and `ResultStore`.
- Produces: `RunOutcome`, `build_initial_messages(...)`,
  `bounded_observation(...)`, and `run_agent(...) -> RunOutcome`.

- [ ] **Step 1: Write a failing scripted-model end-to-end test**

```python
from collections import deque
from pathlib import Path

from agent.loop import run_agent
from agent.ollama import OllamaModel, OllamaReply
from runner.config import BudgetConfig
from runner.manifests import load_manifest
from runner.storage import ResultStore
from tests.test_manifests import write_task


class ScriptedClient:
    def __init__(self, replies: list[str]) -> None:
        self.replies = deque(replies)

    def chat(self, **kwargs: object) -> OllamaReply:
        return OllamaReply(
            content=self.replies.popleft(),
            prompt_tokens=10,
            completion_tokens=5,
            total_duration_ns=1_000_000,
        )


def test_agent_success_requires_fresh_final_test(tmp_path: Path) -> None:
    task = write_task(tmp_path)
    (task / "repo" / "value.py").write_text("value = 1\n", encoding="utf-8")
    tests = task / "repo" / "tests"
    tests.mkdir()
    (tests / "test_value.py").write_text(
        "from value import value\n\ndef test_value(): assert value == 2\n",
        encoding="utf-8",
    )
    client = ScriptedClient(
        [
            '{"action":"apply_patch","patch":"--- a/value.py\\n+++ b/value.py\\n@@ -1 +1 @@\\n-value = 1\\n+value = 2\\n"}',
            '{"action":"finish","summary":"fixed"}',
        ]
    )
    store = ResultStore(tmp_path / "runs.sqlite3")

    outcome = run_agent(
        client=client,
        model=OllamaModel("local:test", "abc", "1B", "Q4"),
        ollama_version="0.test",
        manifest=load_manifest(task),
        budget=BudgetConfig(),
        store=store,
    )

    assert outcome.success is True
    assert outcome.final_test.exit_code == 0
    assert outcome.test_runs == 1
```

Add tests where the model immediately returns `finish` while tests fail,
returns malformed JSON for every turn, and times out. Assert success is false
and a final test is still attempted whenever Python can launch.

- [ ] **Step 2: Verify missing-loop failures**

```powershell
C:\Users\ktubi\anaconda3\python.exe -m pytest tests/test_agent_loop.py -q
```

- [ ] **Step 3: Implement stable prompts**

The system message must state the five actions, one-action-per-response rule,
no Markdown fences, no shell, no protected-test access, budget, and that
`finish` cannot determine success. The task message includes the exact
instruction and sorted file tree with sizes, but not hidden verification
content.

Bound observations to 96 KiB and include explicit markers when truncation
occurs. Return protocol errors as JSON observations so a model can correct its
next response.

- [ ] **Step 4: Implement the loop and authoritative terminal status**

Start storage before the first model call. For each turn:

1. call `client.chat` with the schema and immutable budget;
2. parse one action;
3. execute it;
4. store request/result and timing;
5. append assistant and tool-observation messages;
6. stop only on `Finish` or a terminal error.

After the loop, call `executor.final_test()` exactly once, build the final
diff, and map:

```python
success = final_test.exit_code == 0 and not final_test.timed_out
status = "success" if success else terminal_error_status or "tests_failed"
```

Persist the result in a `finally` path. `RunOutcome` carries run ID, status,
success, duration, turns, test runs, patch, and final test.

- [ ] **Step 5: Run scripted E2E and mutation checks**

```powershell
C:\Users\ktubi\anaconda3\python.exe -m pytest tests/test_agent_loop.py -q
```

Expected: the successful patch passes. Temporarily trusting the `finish`
summary instead of the final test makes the immediate-finish failure test
fail.

- [ ] **Step 6: Commit**

```powershell
git add agent/prompt.py agent/loop.py tests/test_agent_loop.py
git commit -m "feat: run constrained iterative coding agents"
```

---

### Task 9: First vertical corpus slice

**Files:**
- Create all files under:
  `tasks/bug_off_by_one/`,
  `tasks/feature_slugify/`,
  `tasks/test_parse_bool/`,
  `tasks/refactor_pricing/`,
  `tasks/csv_clean_contacts/`,
  `tasks/parse_config_version/`
- Create: `tests/test_corpus.py`

**Interfaces:**
- Consumes: manifest loader and fixed pytest executor.
- Produces: six valid, isolated, initially failing task repositories covering
  every requested category once.

- [ ] **Step 1: Write failing corpus-contract tests**

```python
from pathlib import Path

from agent.executor import WorkspaceExecutor
from runner.manifests import discover_tasks


def test_first_corpus_slice_has_six_tasks() -> None:
    tasks = discover_tasks(Path("tasks"))
    assert len(tasks) == 6
    assert {task.category for task in tasks.values()} == {
        "fix_bug",
        "add_function",
        "write_test",
        "refactor",
        "csv",
        "schema_parsing",
    }


def test_every_initial_repository_fails_its_fixed_tests() -> None:
    for manifest in discover_tasks(Path("tasks")).values():
        with WorkspaceExecutor.create(
            manifest, test_timeout_s=manifest.test_timeout_s
        ) as executor:
            result = executor.final_test()
        assert result.exit_code != 0, manifest.task_id
```

Task 10 replaces this count assertion with the final twelve-task contract.

- [ ] **Step 2: Create six exact task behaviors**

Use only standard-library production code.

1. `bug_off_by_one`: `window(values, start, width)` incorrectly slices through
   `start + width - 1`; tests require exactly `width` elements and empty
   output beyond the end.
2. `feature_slugify`: missing `slugify(text)` must NFKD-normalize, remove
   combining marks, lowercase, replace non-alphanumerics with single hyphens,
   and strip edge hyphens.
3. `test_parse_bool`: `parse_bool` is correct; a public test contains
   `raise AssertionError("replace with assertions for invalid values")`.
   Protected verification parses the public test AST and requires
   `test_parse_bool_rejects_invalid_value`, a `pytest.raises(ValueError)`
   context, and a call using `"sometimes"`.
4. `refactor_pricing`: behavior already passes public examples, but a public
   architecture test fails until `discount_rate(customer_kind, subtotal)` is
   extracted. Protected tests cover standard, member, and VIP boundaries.
5. `csv_clean_contacts`: implement `clean_contacts(input_text)` using
   `csv.DictReader/Writer`; reject missing `email`, trim names, lowercase
   email, skip malformed addresses, deduplicate email, and emit stable
   `name,email` CSV.
6. `parse_config_version`: parser currently accepts string version `"2"`;
   require integer version `2`, required string `name`, and reject unknown
   top-level keys.

Each task gets a French instruction, MIT header where appropriate, manifest,
public tests, and protected behavioral tests. The protected tests import from
`repo` through the temporary test root and do not use external packages beyond
pytest.

- [ ] **Step 3: Run manifest and narrowed baseline validation**

```powershell
C:\Users\ktubi\anaconda3\python.exe -m pytest tests/test_manifests.py tests/test_corpus.py -q
```

Expected: all six manifests load and each initial state fails for its intended
reason.

- [ ] **Step 4: Commit**

```powershell
git add tasks tests/test_corpus.py
git commit -m "feat: add first six synthetic coding tasks"
```

---

### Task 10: Complete the twelve-task corpus

**Files:**
- Create all files under:
  `tasks/bug_cache_key/`,
  `tasks/feature_chunked/`,
  `tasks/test_safe_divide/`,
  `tasks/refactor_normalize_record/`,
  `tasks/csv_sales_summary/`,
  `tasks/parse_event_payload/`
- Modify: `tests/test_corpus.py`

**Interfaces:**
- Consumes: corpus contract from Task 9.
- Produces: the complete two-per-category twelve-task corpus.

- [ ] **Step 1: Add failing manifest expectations for the six IDs**

```python
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
    assert set(discover_tasks(Path("tasks"))) == EXPECTED_IDS
```

Run this test and confirm the six new IDs are missing.

- [ ] **Step 2: Create six exact task behaviors**

1. `bug_cache_key`: cache key currently concatenates namespace and key;
   distinguish `("ab", "c")` from `("a", "bc")` with a tuple key.
2. `feature_chunked`: add `chunked(values, size)` returning tuple chunks,
   preserving the input, accepting any iterable, and raising `ValueError` for
   `size <= 0`.
3. `test_safe_divide`: correct `safe_divide` returns `None` for zero;
   replace the failing placeholder with
   `test_safe_divide_returns_none_for_zero`, one direct call, and an identity
   assertion `is None`; protected AST checks enforce these elements.
4. `refactor_normalize_record`: extract `normalize_email` and
   `normalize_tags` from one large function while preserving missing-field,
   whitespace, case, deduplication, and stable-order behavior.
5. `csv_sales_summary`: parse `sku,quantity,unit_price`, reject negative or
   malformed numeric rows, aggregate revenue per SKU with `Decimal`, and emit
   stable `sku,revenue` rows with two decimals.
6. `parse_event_payload`: require exactly `type`, `timestamp`, and `payload`;
   accept only known event types, parse an ISO-8601 UTC timestamp, require
   object payload, and reject booleans where an integer sequence is expected.

- [ ] **Step 3: Run the full corpus validation**

```powershell
C:\Users\ktubi\anaconda3\python.exe -m pytest tests/test_corpus.py -q
```

Expected: exactly twelve tasks, two per category, every manifest valid, every
initial repository failing, and task sources unchanged.

- [ ] **Step 4: Commit**

```powershell
git add tasks tests/test_corpus.py
git commit -m "feat: complete twelve-task Python corpus"
```

---

### Task 11: Benchmark orchestration and CLI

**Files:**
- Create: `runner/benchmark.py`
- Create: `runner/cli.py`
- Create: `runner/__main__.py`
- Create: `tests/test_benchmark.py`
- Create: `tests/test_cli.py`

**Interfaces:**
- Consumes: configuration, discovered tasks, `OllamaClient`, `run_agent`,
  `ResultStore`.
- Produces: `BenchmarkRunner`, `run_one(model_tag, task_id)`,
  `run_batch()`, and CLI `main(argv: Sequence[str] | None = None) -> int`.

- [ ] **Step 1: Write failing preflight tests**

```python
import pytest

from agent.ollama import ModelMissing
from runner.benchmark import BenchmarkRunner


def test_runner_rejects_missing_model_before_creating_run(config, fake_client) -> None:
    fake_client.models = []
    runner = BenchmarkRunner(config=config, client=fake_client)
    with pytest.raises(ModelMissing):
        runner.run_one("missing:test", "bug_off_by_one")


def test_batch_uses_one_budget_snapshot_for_every_pair(config, fake_client) -> None:
    runner = BenchmarkRunner(config=config, client=fake_client)
    outcomes = runner.run_batch()
    assert outcomes
    assert {item.parameters_json for item in outcomes} == {
        outcomes[0].parameters_json
    }
```

Add CLI tests that capture stdout for `list-models`, ensure `run` requires
both task and model, and verify no code path contains or calls a pull method.

- [ ] **Step 2: Run and observe missing-runner failures**

```powershell
C:\Users\ktubi\anaconda3\python.exe -m pytest tests/test_benchmark.py tests/test_cli.py -q
```

- [ ] **Step 3: Implement the benchmark runner**

At construction, discover tasks, open storage, and cache exact Ollama version
and tag metadata. `run_one` validates exact model/task membership, then calls
`run_agent`. `run_batch` computes the Cartesian product in deterministic
configured order and continues after an individual recorded failure.

Never catch `KeyboardInterrupt`; allow the user to stop a batch. Print one
local progress line per completed pair.

- [ ] **Step 4: Implement argparse commands**

Use subparsers:

```text
list-models [--config PATH]
validate-tasks [--config PATH]
run --model TAG --task ID [--config PATH]
batch [--config PATH]
show-runs [--config PATH] [--limit N]
```

`list-models` prints exact tag, digest prefix, size, and quantization from
`/api/tags`. `validate-tasks` checks manifests and confirms every baseline
fails. `show-runs` reads SQLite only.

- [ ] **Step 5: Run orchestration and CLI tests**

```powershell
C:\Users\ktubi\anaconda3\python.exe -m pytest tests/test_benchmark.py tests/test_cli.py -q
```

- [ ] **Step 6: Commit**

```powershell
git add runner/benchmark.py runner/cli.py runner/__main__.py tests/test_benchmark.py tests/test_cli.py
git commit -m "feat: orchestrate local benchmark runs"
```

---

### Task 12: Dashboard data layer and Plotly figures

**Files:**
- Create: `dashboard/data.py`
- Create: `dashboard/charts.py`
- Create: `examples/demo_results.jsonl`
- Create: `tests/test_dashboard_data.py`
- Create: `tests/test_dashboard_charts.py`

**Interfaces:**
- Consumes: local SQLite database or demo JSONL.
- Produces: `DashboardRun`, `load_sqlite_runs`, `load_demo_runs`,
  `ranking_rows`, `scatter_rows`, `heatmap_matrix`, `ranking_figure`,
  `scatter_figure`, and `heatmap_figure`.

- [ ] **Step 1: Write failing aggregate tests with literal expected values**

```python
from dashboard.data import DashboardRun, heatmap_matrix, ranking_rows, scatter_rows


RUNS = [
    DashboardRun("r1", "m1", "t1", True, 2.0, False),
    DashboardRun("r2", "m1", "t2", False, 6.0, False),
    DashboardRun("r3", "m2", "t1", True, 4.0, False),
]


def test_ranking_uses_success_rate_and_run_count() -> None:
    assert ranking_rows(RUNS) == [
        {"model": "m2", "success_rate": 1.0, "runs": 1},
        {"model": "m1", "success_rate": 0.5, "runs": 2},
    ]


def test_scatter_uses_median_duration() -> None:
    assert scatter_rows(RUNS) == [
        {"model": "m1", "success_rate": 0.5, "median_duration_s": 4.0},
        {"model": "m2", "success_rate": 1.0, "median_duration_s": 4.0},
    ]


def test_heatmap_preserves_missing_cells() -> None:
    matrix = heatmap_matrix(RUNS)
    assert matrix.models == ("m1", "m2")
    assert matrix.tasks == ("t1", "t2")
    assert matrix.values == ((1.0, 0.0), (1.0, None))
```

- [ ] **Step 2: Verify missing dashboard modules**

```powershell
C:\Users\ktubi\anaconda3\python.exe -m pytest tests/test_dashboard_data.py tests/test_dashboard_charts.py -q
```

- [ ] **Step 3: Implement local loaders and pure aggregation**

`load_sqlite_runs` rejects a missing database and returns only finalized rows.
`load_demo_runs` requires every JSON object to contain `is_demo: true`; a
false/missing marker raises `DashboardDataError`. Use `statistics.median` and
literal arithmetic, with deterministic model/task sorting.

Create eight fictional demo runs across two clearly fake model tags and four
task IDs. Include instruction, action list, final patch, and pytest output in
every JSONL row. Prefix model tags with `demo/`.

- [ ] **Step 4: Implement Plotly figure builders**

`ranking_figure` creates a horizontal bar chart, `scatter_figure` creates one
point per model with hover run metadata, and `heatmap_figure` uses a
three-state colorscale with annotations for pass/fail/missing. Do not load a
remote template, image, or font.

- [ ] **Step 5: Run data and figure tests**

```powershell
C:\Users\ktubi\anaconda3\python.exe -m pytest tests/test_dashboard_data.py tests/test_dashboard_charts.py -q
```

Expected: literal aggregates and Plotly trace shapes match.

- [ ] **Step 6: Commit**

```powershell
git add dashboard/data.py dashboard/charts.py examples/demo_results.jsonl tests/test_dashboard_data.py tests/test_dashboard_charts.py
git commit -m "feat: add local dashboard analytics"
```

---

### Task 13: Streamlit application and smoke validation

**Files:**
- Create: `dashboard/app.py`
- Create: `tests/test_dashboard_smoke.py`

**Interfaces:**
- Consumes: `results/codepulse.sqlite3` or `examples/demo_results.jsonl`.
- Produces: a local four-view Streamlit dashboard with visible scope warning.

- [ ] **Step 1: Write a failing Streamlit AppTest**

```python
from streamlit.testing.v1 import AppTest


def test_demo_dashboard_shows_badge_warning_and_charts(monkeypatch) -> None:
    monkeypatch.setenv("CODEPULSE_DEMO", "1")
    app = AppTest.from_file("dashboard/app.py")
    app.run(timeout=20)
    assert not app.exception
    assert any("DEMO" in item.value for item in app.warning)
    assert any("ce corpus" in item.value.lower() for item in app.warning)
    assert len(app.get("plotly_chart")) >= 3
```

- [ ] **Step 2: Verify the app is missing**

```powershell
C:\Users\ktubi\anaconda3\python.exe -m pytest tests/test_dashboard_smoke.py -q
```

- [ ] **Step 3: Implement the dashboard**

Set wide layout and a local title. A sidebar selects:

- normal SQLite path, default `results/codepulse.sqlite3`;
- demo mode when `CODEPULSE_DEMO=1` or a sidebar checkbox is enabled;
- a specific run for detail.

Render ranking, scatter, and heatmap at the top. Render detail metadata,
instruction, action JSON, patch, stdout, and stderr in tabs. Display this
warning on every rerun:

```text
Ces résultats ne valent que pour ce corpus, ce matériel, cette version
d’Ollama et des modèles, et ces paramètres. Ils ne constituent pas un
classement général de qualité.
```

Demo mode adds a separate warning that all displayed results are fictional.

- [ ] **Step 4: Run AppTest and headless server smoke**

```powershell
C:\Users\ktubi\anaconda3\python.exe -m pytest tests/test_dashboard_smoke.py -q
$env:CODEPULSE_DEMO='1'
C:\Users\ktubi\anaconda3\python.exe -m streamlit run dashboard/app.py --server.headless true --server.port 18501
```

Observe the local startup URL, then stop the server. No browser or external URL
is opened.

- [ ] **Step 5: Commit**

```powershell
git add dashboard/app.py tests/test_dashboard_smoke.py
git commit -m "feat: build local benchmark dashboard"
```

---

### Task 14: MIT licensing and reproducibility documentation

**Files:**
- Create: `LICENSE`
- Create: `README.md`
- Create: `.gitignore`
- Create: `docs/result-format.md`
- Create: `docs/task-format.md`

**Interfaces:**
- Consumes: implemented CLI, schema, config, and dashboard behavior.
- Produces: exact offline operating instructions and documented formats.

- [ ] **Step 1: Write the MIT license and ignore only generated state**

Use the standard MIT text with:

```text
Copyright (c) 2026 CodePulse Local contributors
```

`.gitignore` ignores virtual environments, bytecode, pytest/Streamlit caches,
`results/*.sqlite3`, temporary files, and generated logs. It must not ignore
tasks, demo data, documentation, or configuration.

- [ ] **Step 2: Document offline setup and commands**

README sections:

1. precise benchmark question and disclaimer;
2. requirements: Python 3.12, local Git, already provisioned pytest,
   Streamlit, Plotly, and Ollama;
3. local wheelhouse example using `pip install --no-index --find-links`;
4. direct `ollama serve` startup and API health check;
5. `list-models`, task validation, single run, batch, and dashboard commands;
6. architecture and action protocol;
7. fixed default budget and result fields;
8. demo mode command;
9. model/license separation and no-weight policy;
10. trust boundary and prohibition on arbitrary repositories;
11. reproducibility limits and current Python 3.13 dashboard-verification
    exception;
12. explicit statement that the harness has no publish, telemetry, pull, or
    external API feature.

Do not include a network installation command. The only dependency example
must use:

```powershell
py -3.12 -m pip install --no-index --find-links D:\wheelhouse -e .[test]
```

- [ ] **Step 3: Document JSON manifest and SQLite result schemas**

`docs/task-format.md` includes one valid complete manifest and describes the
editable/protected split. `docs/result-format.md` lists every `runs` and
`actions` column, terminal status, time unit, nullability, and the
`is_demo` rule.

- [ ] **Step 4: Validate docs against live CLI help**

```powershell
C:\Users\ktubi\anaconda3\python.exe -m runner.cli --help
C:\Users\ktubi\anaconda3\python.exe -m runner.cli run --help
git diff --check
```

Compare the output with README commands and correct any mismatch.

- [ ] **Step 5: Commit**

```powershell
git add LICENSE README.md .gitignore docs/result-format.md docs/task-format.md
git commit -m "docs: explain offline reproducible benchmarking"
```

---

### Task 15: Full verification and real installed-model run

**Files:**
- Modify only files whose failing verification demonstrates a defect.
- Create generated local result: `results/codepulse.sqlite3` (ignored by Git).
- Create: `docs/verification-2026-07-27.md`

**Interfaces:**
- Consumes: complete project and already installed Ollama models.
- Produces: fresh evidence for tests, corpus baselines, dashboard, one real
  model/task run, and requirement coverage.

- [ ] **Step 1: Run the full local test suite**

```powershell
C:\Users\ktubi\anaconda3\python.exe -m pytest -q
```

Expected: zero failures. Record exact count and duration.

- [ ] **Step 2: Verify Python 3.12 source compatibility**

```powershell
py -3.12 -m compileall -q agent runner dashboard tests
```

Expected: exit zero. Remove generated `__pycache__` directories through the
normal ignored-file cleanup mechanism, not by altering source.

- [ ] **Step 3: Validate all twelve initial task states**

```powershell
C:\Users\ktubi\anaconda3\python.exe -m runner.cli validate-tasks
```

Expected: twelve valid tasks and twelve expected failing baselines.

- [ ] **Step 4: Start Ollama server-only and re-list installed tags**

Launch the server executable directly with `ollama serve`, not Ollama Desktop.
Confirm `GET http://127.0.0.1:11434/api/version`, then run:

```powershell
C:\Users\ktubi\anaconda3\python.exe -m runner.cli list-models
```

Verify the selected tag is present. Do not invoke a pull and do not start the
desktop updater.

- [ ] **Step 5: Run one real local vertical path**

First attempt:

```powershell
C:\Users\ktubi\anaconda3\python.exe -m runner.cli run --model qwen3:8b --task bug_off_by_one
```

If local hardware cannot load the installed 8B model, record that failure and
run the already installed fallback:

```powershell
C:\Users\ktubi\anaconda3\python.exe -m runner.cli run --model qwen2.5:1.5b --task bug_off_by_one
```

Do not alter the recorded outcome. Query the resulting SQLite row and verify
model tag/digest, Ollama version, parameters, date, task, status, duration,
turns, test count, final patch, actions, and final pytest output.

- [ ] **Step 6: Re-run the full suite after real execution**

```powershell
C:\Users\ktubi\anaconda3\python.exe -m pytest -q
git status --short
git diff --check
```

Expected: zero failures; only ignored runtime results and the verification
document may be new.

- [ ] **Step 7: Write the verification report**

`docs/verification-2026-07-27.md` records exact commands, interpreter
versions, dependency versions, test counts, task-validation count, real run
ID and observed success/failure, dashboard smoke result, the Python 3.13
exception, hardware limitations, and the Ollama Desktop updater incident.

- [ ] **Step 8: Commit verification evidence**

```powershell
git add docs/verification-2026-07-27.md
git commit -m "test: record local benchmark verification"
```

---

### Task 16: Requirement audit and delivery to requested path

**Files:**
- Inspect: all tracked files and `docs/superpowers/specs/2026-07-27-codepulse-local-design.md`
- Create destination: `D:\projet\fin\codepulse-local`

**Interfaces:**
- Consumes: verified source repository.
- Produces: complete local Git repository at the user-requested destination.

- [ ] **Step 1: Audit every explicit requirement**

Create a checklist from the approved design and original request. For each
item, cite direct evidence: file path, test name, command output, SQLite row,
or dashboard smoke result. Any missing or indirect evidence returns to the
owning task before delivery.

- [ ] **Step 2: Verify no external/pull/publish code path exists**

```powershell
rg -n -i "api/pull|ollama pull|github|telemetry|requests\.|urllib\.request|https://" agent runner dashboard tasks README.md
```

Review every match. Allowed matches are explanatory documentation and the MIT
license; executable code must contain no pull, hosted endpoint, telemetry, or
publish implementation.

- [ ] **Step 3: Verify repository contents and licenses**

```powershell
git ls-files
rg --files | rg -i "\.(gguf|safetensors|bin|pt|pth)$"
git status --short
```

Expected: no model-weight file, clean tracked state, and all project-owned
artifacts covered by the root MIT license.

- [ ] **Step 4: Copy without overwriting an unexpected destination**

Confirm `D:\projet\fin\codepulse-local` does not exist. Create its parent,
then copy the complete repository, including `.git`, with PowerShell
`Copy-Item -Recurse`. If the destination exists, stop and compare rather than
delete, mirror, or overwrite it.

- [ ] **Step 5: Verify the delivered copy independently**

```powershell
git -C D:\projet\fin\codepulse-local status --short
C:\Users\ktubi\anaconda3\python.exe -m pytest -q D:\projet\fin\codepulse-local\tests
```

Run the second command with working directory
`D:\projet\fin\codepulse-local`. Confirm the destination repository is clean
and the full suite passes there.

- [ ] **Step 6: Report launch commands and evidence**

Return exact commands for server-only Ollama, model listing, validation, one
run, batch, normal dashboard, and demo dashboard. Report test count, observed
real-model result, Python-version exception, trust boundary, and important
files using absolute clickable paths.
