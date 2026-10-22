from dataclasses import dataclass
import json
from pathlib import Path
import re


class ManifestError(ValueError):
    pass


_VALID_ID_RE = re.compile(r"^[a-z][a-z0-9_]{2,63}$")


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
    solution_path: Path | None = None
    mutants_path: Path | None = None

    def instruction(self) -> str:
        return self.instruction_path.read_text(encoding="utf-8")


def load_manifest(task_dir: Path) -> TaskManifest:
    t_dir = task_dir.resolve()
    manifest_file = t_dir / "manifest.json"
    if not manifest_file.is_file():
        raise ManifestError(f"manifest.json missing in task directory: {t_dir}")

    try:
        data = json.loads(manifest_file.read_text(encoding="utf-8"))
    except Exception as err:
        raise ManifestError(f"Failed to parse manifest.json in {t_dir}: {err}") from err

    if not isinstance(data, dict):
        raise ManifestError(f"manifest.json in {t_dir} must be a JSON object")

    task_id = data.get("id")
    if not isinstance(task_id, str) or not _VALID_ID_RE.match(task_id):
        raise ManifestError(f"Invalid task ID '{task_id}' in {t_dir}")

    category = data.get("category")
    if not isinstance(category, str) or not category:
        raise ManifestError(f"Missing category in {t_dir}")

    rel_inst = data.get("instruction", "instruction.md")
    inst_path = (t_dir / rel_inst).resolve()
    if not inst_path.is_relative_to(t_dir) or not inst_path.is_file():
        raise ManifestError(f"Invalid instruction path '{rel_inst}' in {t_dir}")

    rel_repo = data.get("repo", "repo")
    repo_path = (t_dir / rel_repo).resolve()
    if not repo_path.is_relative_to(t_dir) or not repo_path.is_dir():
        raise ManifestError(f"Invalid repo directory path '{rel_repo}' in {t_dir}")

    rel_verif = data.get("verification", "verification")
    verif_path = (t_dir / rel_verif).resolve()
    if not verif_path.is_relative_to(t_dir) or not verif_path.is_dir():
        raise ManifestError(f"Invalid verification directory path '{rel_verif}' in {t_dir}")

    raw_argv = data.get("test_argv")
    if not isinstance(raw_argv, list) or not raw_argv:
        raise ManifestError(f"test_argv in {t_dir} must be a non-empty argument array")

    if not all(isinstance(arg, str) for arg in raw_argv):
        raise ManifestError(f"test_argv elements in {t_dir} must be strings")

    test_argv = tuple(raw_argv)
    if len(test_argv) < 3 or test_argv[0] != "{python}" or test_argv[1] != "-m" or test_argv[2] != "pytest":
        raise ManifestError(f"test_argv in {t_dir} must begin with ['{{python}}', '-m', 'pytest']")

    test_timeout = float(data.get("test_timeout_s", 30.0))
    if test_timeout <= 0:
        raise ManifestError(f"test_timeout_s in {t_dir} must be positive")

    # Reference solution: files overlaid on the repo copy; never exposed to the model.
    solution_path = _optional_task_dir(t_dir, data, "solution")
    # Mutants: buggy variants the agent's own tests must catch (test-writing tasks).
    mutants_path = _optional_task_dir(t_dir, data, "mutants")

    return TaskManifest(
        task_id=task_id,
        category=category,
        task_dir=t_dir,
        instruction_path=inst_path,
        repo_path=repo_path,
        verification_path=verif_path,
        test_argv=test_argv,
        test_timeout_s=test_timeout,
        solution_path=solution_path,
        mutants_path=mutants_path,
    )


def _optional_task_dir(t_dir: Path, data: dict, key: str) -> Path | None:
    rel = data.get(key)
    if rel is None:
        default = t_dir / key
        return default if default.is_dir() else None

    path = (t_dir / rel).resolve()
    if not path.is_relative_to(t_dir) or not path.is_dir():
        raise ManifestError(f"Invalid {key} directory path '{rel}' in {t_dir}")
    return path


def discover_tasks(root: Path) -> dict[str, TaskManifest]:
    tasks_dir = root.resolve()
    if not tasks_dir.is_dir():
        return {}

    manifests: dict[str, TaskManifest] = {}
    for entry in sorted(tasks_dir.iterdir()):
        if entry.is_dir() and (entry / "manifest.json").exists():
            manifest = load_manifest(entry)
            if manifest.task_id in manifests:
                raise ManifestError(f"Duplicate task ID '{manifest.task_id}' discovered in {entry}")
            manifests[manifest.task_id] = manifest

    return manifests
