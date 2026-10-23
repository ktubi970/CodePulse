from collections.abc import Callable
import difflib
from pathlib import Path
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


# A rename or copy reads a source path that `git apply --numstat` does not report.
FORBIDDEN_HEADERS = ("rename from ", "rename to ", "copy from ", "copy to ")


def validate_patch(patch: str, max_bytes: int = 262144) -> None:
    if not isinstance(patch, str) or not patch.strip():
        raise PatchError("Patch must be a non-empty string")

    patch_bytes = patch.encode("utf-8")
    if len(patch_bytes) > max_bytes:
        raise PatchError(f"Patch exceeds maximum size limit of {max_bytes} bytes")

    for marker in FORBIDDEN_MARKERS:
        if marker in patch:
            raise PatchError(f"Patch contains forbidden header/binary marker: '{marker}'")

    for line in patch.splitlines():
        if line.startswith(FORBIDDEN_HEADERS):
            raise PatchError(f"Patch renames or copies files, which is not supported: '{line}'")


def _git_apply(root: Path, patch: str, *options: str) -> str:
    try:
        proc = subprocess.run(
            ["git", "apply", *options, "--whitespace=nowarn", "-"],
            cwd=root.resolve(),
            input=patch.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            timeout=10,
            check=False,
        )
    except Exception as err:
        raise PatchError(f"Failed to execute git apply {' '.join(options)}: {err}") from err

    if proc.returncode != 0:
        err_msg = proc.stderr.decode("utf-8", errors="replace").strip()
        raise PatchError(f"git apply {' '.join(options)} failed: {err_msg}")
    return proc.stdout.decode("utf-8", errors="replace")


def patch_paths(root: Path, patch: str) -> tuple[str, ...]:
    """Every path the patch creates, modifies or deletes, as `git apply` itself reads it."""
    paths: set[str] = set()
    for record in _git_apply(root, patch, "--numstat", "-z").split("\0"):
        if not record:
            continue
        fields = record.split("\t")
        if len(fields) != 3 or not fields[2]:
            raise PatchError(f"Unexpected git apply --numstat record: {record!r}")
        paths.add(fields[2])
    if not paths:
        raise PatchError("Patch does not specify any file changes")
    return tuple(sorted(paths))


def apply_patch(root: Path, patch: str, check_path: Callable[[str], object]) -> tuple[str, ...]:
    """Apply a unified diff once `check_path` has accepted every path it touches."""
    validate_patch(patch)
    changed_paths = patch_paths(root, patch)
    for path in changed_paths:
        check_path(path)
    _git_apply(root, patch, "--check")
    _git_apply(root, patch)
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
