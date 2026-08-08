import difflib
from pathlib import Path, PurePosixPath
import subprocess
from typing import Mapping


class PatchError(ValueError):
    pass


FORBIDDEN_MARKERS = (
    "GIT binary patch",
    "Binary files ",
    "new file mode 120000",
    "old mode ",
    "new mode ",
    "Subproject commit ",
)


def snapshot_tree(root: Path) -> dict[str, bytes]:
    root_resolved = root.resolve()
    snapshot: dict[str, bytes] = {}

    skip_dirs = {"__pycache__", ".pytest_cache", ".git", ".venv", "venv", "node_modules"}

    for path in sorted(root_resolved.rglob("*")):
        if path.is_file():
            if any(part in skip_dirs for part in path.parts):
                continue
            if path.stat().st_size > 1024 * 1024:  # > 1 MiB skip/reject
                continue
            try:
                rel_path = path.relative_to(root_resolved).as_posix()
                content = path.read_bytes()
                if b"\x00" in content:  # Binary NUL check
                    continue
                snapshot[rel_path] = content
            except Exception:
                continue

    return snapshot


def validate_patch(patch: str, max_bytes: int = 262144) -> tuple[str, ...]:
    if not isinstance(patch, str) or not patch.strip():
        raise PatchError("Patch must be a non-empty string")

    patch_bytes = patch.encode("utf-8")
    if len(patch_bytes) > max_bytes:
        raise PatchError(f"Patch exceeds maximum size limit of {max_bytes} bytes")

    for marker in FORBIDDEN_MARKERS:
        if marker in patch:
            raise PatchError(f"Patch contains forbidden header/binary marker: '{marker}'")

    changed_files: set[str] = set()
    lines = patch.splitlines()

    for line in lines:
        if line.startswith("--- ") or line.startswith("+++ "):
            target = line[4:].strip()
            if "\t" in target:
                target = target.split("\t")[0]

            if target == "/dev/null":
                continue

            # Strip standard git patch prefixes (a/ or b/)
            if target.startswith("a/") or target.startswith("b/"):
                target = target[2:]

            posix_path = PurePosixPath(target.replace("\\", "/"))
            if posix_path.is_absolute() or ".." in posix_path.parts:
                raise PatchError(f"Patch references invalid or traversing path: '{target}'")

            changed_files.add(posix_path.as_posix())

    if not changed_files:
        raise PatchError("Patch does not specify any file changes")

    return tuple(sorted(changed_files))


def apply_patch(root: Path, patch: str) -> tuple[str, ...]:
    changed_paths = validate_patch(patch)
    root_resolved = root.resolve()

    # Pre-check dry run
    try:
        check = subprocess.run(
            ["git", "apply", "--check", "--whitespace=nowarn", "-"],
            cwd=root_resolved,
            input=patch.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            timeout=10,
            check=False,
        )
    except Exception as err:
        raise PatchError(f"Failed to execute git apply --check: {err}") from err

    if check.returncode != 0:
        err_msg = check.stderr.decode("utf-8", errors="replace").strip()
        raise PatchError(f"git apply --check failed: {err_msg}")

    # Actual application
    try:
        apply_res = subprocess.run(
            ["git", "apply", "--whitespace=nowarn", "-"],
            cwd=root_resolved,
            input=patch.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            timeout=10,
            check=False,
        )
    except Exception as err:
        raise PatchError(f"Failed to execute git apply: {err}") from err

    if apply_res.returncode != 0:
        err_msg = apply_res.stderr.decode("utf-8", errors="replace").strip()
        raise PatchError(f"git apply failed: {err_msg}")

    return changed_paths


def build_final_diff(before: Mapping[str, bytes], after: Mapping[str, bytes]) -> str:
    all_keys = sorted(set(before.keys()) | set(after.keys()))
    diff_parts = []

    for path in all_keys:
        before_bytes = before.get(path)
        after_bytes = after.get(path)

        if before_bytes == after_bytes:
            continue

        before_lines = (
            before_bytes.decode("utf-8", errors="replace").splitlines(keepends=True)
            if before_bytes is not None
            else []
        )
        after_lines = (
            after_bytes.decode("utf-8", errors="replace").splitlines(keepends=True)
            if after_bytes is not None
            else []
        )

        from_file = f"a/{path}" if before_bytes is not None else "/dev/null"
        to_file = f"b/{path}" if after_bytes is not None else "/dev/null"

        diff = list(
            difflib.unified_diff(
                before_lines,
                after_lines,
                fromfile=from_file,
                tofile=to_file,
                lineterm="\n",
            )
        )
        if diff:
            diff_parts.extend(diff)

    return "".join(diff_parts)
