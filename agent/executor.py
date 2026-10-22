from dataclasses import dataclass, field
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Self, Sequence
import uuid
from xml.etree import ElementTree

from agent.patches import apply_patch as sys_apply_patch, build_final_diff, snapshot_tree
from agent.protocol import Action, ApplyPatch, Finish, ListFiles, ReadFile, RunTests, WriteFile
from runner.manifests import TaskManifest

# -I ignores PYTHON* variables, user site-packages and the working directory, so files
# written by the model (sitecustomize.py, ...) are not importable at interpreter start-up.
# The repository only joins sys.path later, through pytest's `pythonpath` option.
# -B keeps __pycache__ out of the workspace.
_PYTHON_FLAGS = ("-I", "-B")
# conftest.py hooks written by the model could rewrite test outcomes.
_PYTEST_FLAGS = ("--noconftest", "-p", "no:cacheprovider", "-o", "pythonpath=repo")
# Mutants are checked against the repository's own tests, i.e. the tests the agent wrote.
_MUTATION_ARGV = ("-q", "repo/tests")


class ExecutorError(RuntimeError):
    pass


def _sanitized_env() -> dict[str, str]:
    env = {
        key: os.environ[key]
        for key in ("PATH", "SYSTEMROOT", "TEMP", "TMP", "PATHEXT", "COMSPEC")
        if key in os.environ
    }
    env.update(
        {
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
            "NO_PROXY": "*",
            "no_proxy": "*",
        }
    )
    return env


def check_test_runtime(python: str | None = None, module: str = "pytest") -> str:
    """Fail loudly when the isolated test command cannot start.

    Isolated mode (-I) disables user site-packages, so a pytest installed with
    `pip install --user` is invisible to it and every run would silently fail.
    """
    argv = [python or sys.executable, *_PYTHON_FLAGS, "-m", module, "--version"]
    try:
        proc = subprocess.run(
            argv, env=_sanitized_env(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60, check=False
        )
    except Exception as err:
        raise ExecutorError(f"Test runtime check failed to launch {argv[0]}: {err}") from err

    output = (proc.stdout + proc.stderr).decode("utf-8", errors="replace").strip()
    if proc.returncode != 0:
        raise ExecutorError(
            f"The test runner cannot import '{module}' with {argv[0]} (user site-packages are disabled): "
            f"{output}\nInstall the project in a virtual environment: python -m venv .venv, "
            "then pip install -e .[test] inside it."
        )
    return output


@dataclass(frozen=True, slots=True)
class TestReport:
    tests: int
    failures: int
    errors: int
    skipped: int


def _read_junit(path: Path) -> TestReport | None:
    try:
        root = ElementTree.parse(path).getroot()
    except (OSError, ElementTree.ParseError):
        return None
    suites = [root] if root.tag == "testsuite" else root.findall("testsuite")
    if not suites:
        return None
    try:
        totals = [sum(int(s.get(key, "0")) for s in suites) for key in ("tests", "failures", "errors", "skipped")]
    except ValueError:
        return None
    return TestReport(*totals)


@dataclass(frozen=True, slots=True)
class TestResult:
    exit_code: int | None
    stdout: str
    stderr: str
    timed_out: bool = False
    duration_s: float = 0.0
    report: TestReport | None = None

    @property
    def passed(self) -> bool:
        # Exit code 0 alone is not proof: code under test can os._exit(0) or skip tests.
        return (
            self.exit_code == 0
            and not self.timed_out
            and self.report is not None
            and self.report.tests > 0
            and self.report.failures == self.report.errors == self.report.skipped == 0
        )


@dataclass(frozen=True, slots=True)
class ActionResult:
    kind: str
    data: dict[str, Any] = field(default_factory=dict)


class WorkspaceExecutor:
    def __init__(self, manifest: TaskManifest, test_timeout_s: float | None = None) -> None:
        self.manifest = manifest
        self.test_timeout_s = test_timeout_s if test_timeout_s is not None else manifest.test_timeout_s
        self._temp_dir: str | None = None
        self.work_dir: Path | None = None
        self.repo_root: Path | None = None
        self.verification_root: Path | None = None
        self.initial_snapshot: dict[str, bytes] = {}
        self.test_run_count: int = 0

    @classmethod
    def create(cls, manifest: TaskManifest, test_timeout_s: float | None = None) -> "WorkspaceExecutor":
        executor = cls(manifest, test_timeout_s=test_timeout_s)
        executor.setup()
        return executor

    def setup(self) -> None:
        self._temp_dir = tempfile.mkdtemp(prefix="codepulse_run_")
        self.work_dir = Path(self._temp_dir).resolve()

        self.repo_root = self.work_dir / "repo"
        self.verification_root = self.work_dir / "verification"

        shutil.copytree(self.manifest.repo_path, self.repo_root)
        shutil.copytree(self.manifest.verification_path, self.verification_root)

        self.initial_snapshot = snapshot_tree(self.repo_root)

    def cleanup(self) -> None:
        if self._temp_dir and os.path.exists(self._temp_dir):
            try:
                shutil.rmtree(self._temp_dir, ignore_errors=True)
            except Exception:
                pass
            self._temp_dir = None
            self.work_dir = None
            self.repo_root = None
            self.verification_root = None

    def __enter__(self) -> Self:
        if self.work_dir is None:
            self.setup()
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        self.cleanup()

    def overlay(self, source_dir: Path) -> None:
        """Copy a tree (reference solution, mutant) over the editable repository."""
        if self.repo_root is None:
            raise ExecutorError("Executor workspace is not setup")
        shutil.copytree(source_dir, self.repo_root, dirs_exist_ok=True)

    def _resolve_relative_path(self, path_str: str) -> Path:
        if self.repo_root is None:
            raise ExecutorError("Executor workspace is not setup")

        clean_rel = PurePosixPath(path_str.replace("\\", "/"))
        if clean_rel.is_absolute() or ".." in clean_rel.parts:
            raise ExecutorError(f"Path '{path_str}' escapes editable repository")

        candidate = (self.repo_root / clean_rel).resolve()
        if not candidate.is_relative_to(self.repo_root.resolve()):
            raise ExecutorError(f"Path '{path_str}' resolves outside editable repository")

        return candidate

    def list_files(self) -> ActionResult:
        if self.repo_root is None:
            raise ExecutorError("Executor workspace is not setup")

        entries: list[str] = []
        skip_dirs = {"__pycache__", ".pytest_cache", ".git", ".venv", "venv"}

        for p in sorted(self.repo_root.rglob("*")):
            if p.is_file():
                if any(part in skip_dirs for part in p.parts):
                    continue
                try:
                    rel_p = p.relative_to(self.repo_root).as_posix()
                    size = p.stat().st_size
                    entries.append(f"{rel_p}\t{size} bytes")
                except Exception:
                    continue

        listing = "\n".join(entries) if entries else "No files found."
        return ActionResult(kind="list_files", data={"listing": listing})

    def read_file(self, path_str: str) -> ActionResult:
        target = self._resolve_relative_path(path_str)
        if not target.is_file():
            raise ExecutorError(f"File not found: '{path_str}'")

        if target.is_symlink():
            raise ExecutorError(f"Symlinks are forbidden: '{path_str}'")

        size = target.stat().st_size
        if size > 65536:  # 64 KiB ceiling
            raise ExecutorError(f"File '{path_str}' exceeds maximum read size of 64 KiB ({size} bytes)")

        try:
            content = target.read_text(encoding="utf-8")
        except Exception as err:
            raise ExecutorError(f"Failed to read '{path_str}' as UTF-8: {err}") from err

        return ActionResult(kind="read_file", data={"path": path_str, "content": content})

    def write_file(self, path_str: str, content: str) -> ActionResult:
        target = self._resolve_relative_path(path_str)
        if target.is_dir():
            raise ExecutorError(f"Cannot write '{path_str}': it is a directory")

        data = content.encode("utf-8")
        if len(data) > 65536:  # same ceiling as read_file
            raise ExecutorError(f"Content for '{path_str}' exceeds maximum write size of 64 KiB ({len(data)} bytes)")

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)  # bytes: no platform newline translation
        return ActionResult(kind="write_file", data={"path": path_str, "bytes_written": len(data), "ok": True})

    def apply_patch(self, patch: str) -> ActionResult:
        if self.repo_root is None:
            raise ExecutorError("Executor workspace is not setup")

        try:
            changed = sys_apply_patch(self.repo_root, patch)
            return ActionResult(kind="apply_patch", data={"changed_files": list(changed), "ok": True})
        except Exception as err:
            raise ExecutorError(f"Failed to apply patch: {err}") from err

    def run_tests(self) -> ActionResult:
        result = self._execute_pytest_vector()
        self.test_run_count += 1
        return ActionResult(
            kind="test_result",
            data={
                "exit_code": result.exit_code,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "timed_out": result.timed_out,
            },
        )

    def finish(self, summary: str) -> ActionResult:
        return ActionResult(kind="finish", data={"summary": summary})

    def execute(self, action: Action) -> ActionResult:
        if isinstance(action, ListFiles):
            return self.list_files()
        elif isinstance(action, ReadFile):
            return self.read_file(action.path)
        elif isinstance(action, WriteFile):
            return self.write_file(action.path, action.content)
        elif isinstance(action, ApplyPatch):
            return self.apply_patch(action.patch)
        elif isinstance(action, RunTests):
            return self.run_tests()
        elif isinstance(action, Finish):
            return self.finish(action.summary)
        else:
            raise ExecutorError(f"Unsupported action type: {type(action)}")

    def _execute_pytest_vector(self, argv_tail: Sequence[str] | None = None, cwd: Path | None = None) -> TestResult:
        if self.work_dir is None:
            raise ExecutorError("Executor workspace is not setup")

        # The manifest vector always starts with {python} -m pytest (enforced by the loader).
        tail = self.manifest.test_argv[3:] if argv_tail is None else argv_tail
        report_path = self.work_dir / f"junit-{uuid.uuid4().hex}.xml"
        argv = [
            sys.executable, *_PYTHON_FLAGS, "-m", "pytest", *_PYTEST_FLAGS, f"--junitxml={report_path}", *tail
        ]

        try:
            proc = subprocess.run(
                argv,
                cwd=cwd or self.work_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=_sanitized_env(),
                timeout=self.test_timeout_s,
                shell=False,
                check=False,
            )
            stdout = proc.stdout.decode("utf-8", errors="replace")[:262144]
            stderr = proc.stderr.decode("utf-8", errors="replace")[:262144]
            report = _read_junit(report_path)
            report_path.unlink(missing_ok=True)
            return TestResult(exit_code=proc.returncode, stdout=stdout, stderr=stderr, timed_out=False, report=report)
        except subprocess.TimeoutExpired as exc:
            stdout = (exc.stdout or b"").decode("utf-8", errors="replace")[:262144]
            stderr = (exc.stderr or b"").decode("utf-8", errors="replace")[:262144]
            return TestResult(
                exit_code=None, stdout=stdout, stderr=stderr + "\nTest run timed out.", timed_out=True
            )
        except Exception as err:
            return TestResult(
                exit_code=1, stdout="", stderr=f"Failed to launch pytest command vector: {err}", timed_out=False
            )

    def final_test(self) -> TestResult:
        return self._execute_pytest_vector()

    def surviving_mutants(self) -> list[str]:
        """Names of known-buggy variants that the repository's own tests fail to catch.

        A test-writing task is not solved by deleting the failing test: the agent's tests
        must also fail on each mutant shipped with the task.
        """
        if self.manifest.mutants_path is None:
            return []
        if self.work_dir is None or self.repo_root is None:
            raise ExecutorError("Executor workspace is not setup")

        survivors: list[str] = []
        for mutant in sorted(p for p in self.manifest.mutants_path.iterdir() if p.is_dir()):
            mutant_root = self.work_dir / "mutants" / mutant.name
            shutil.rmtree(mutant_root, ignore_errors=True)
            shutil.copytree(self.repo_root, mutant_root / "repo")
            shutil.copytree(mutant, mutant_root / "repo", dirs_exist_ok=True)
            if self._execute_pytest_vector(_MUTATION_ARGV, cwd=mutant_root).exit_code == 0:
                survivors.append(mutant.name)
        return survivors

    def final_diff(self) -> str:
        if self.repo_root is None:
            return ""
        current_snapshot = snapshot_tree(self.repo_root)
        return build_final_diff(self.initial_snapshot, current_snapshot)
