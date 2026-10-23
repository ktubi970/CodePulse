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
class WriteFile:
    path: str
    content: str
    action: str = "write_file"


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


Action: TypeAlias = ListFiles | ReadFile | WriteFile | ApplyPatch | RunTests | Finish

# Fields each action needs. Other schema fields are tolerated and ignored: the flat schema
# sent to Ollama lets constrained decoding emit them, so rejecting them punishes the model
# for output the harness itself allowed.
_REQUIRED_FIELDS: dict[str, frozenset[str]] = {
    "list_files": frozenset(),
    "read_file": frozenset({"path"}),
    "write_file": frozenset({"path", "content"}),
    "apply_patch": frozenset({"patch"}),
    "run_tests": frozenset(),
    "finish": frozenset(),
}
_SCHEMA_FIELDS = frozenset({"action", "path", "patch", "content", "summary"})


def relative_path(value: object) -> str:
    """The one rule for every path the model supplies, whether in an action field or inside a patch."""
    if not isinstance(value, str) or not value.strip():
        raise ProtocolError("path must be a non-empty relative path")
    path_str = value.replace("\\", "/").strip()
    path = PurePosixPath(path_str)
    # ':' covers Windows drives (C:/x) and NTFS alternate data streams (x.py:stream).
    if path.is_absolute() or ".." in path.parts or ":" in path_str:
        raise ProtocolError(
            "path must be relative to the repository root (e.g. 'src/file.py') and cannot traverse parents"
        )
    return path.as_posix()


def parse_action(raw: str) -> Action:
    if not isinstance(raw, str):
        raise ProtocolError("raw response must be a string")
    
    if len(raw.encode("utf-8")) > 262144:  # 256 KiB limit
        raise ProtocolError("action response exceeds size ceiling")

    # Strip potential outer codeblock markdown wrapper if models mistakenly include it
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 2 and lines[-1].strip() == "```":
            text = "\n".join(lines[1:-1]).strip()

    try:
        data = json.loads(text)
    except Exception as err:
        raise ProtocolError(f"Response must be valid JSON: {err}") from err

    if not isinstance(data, dict):
        raise ProtocolError("JSON response must be an object")

    action_type = data.get("action")
    if not isinstance(action_type, str):
        raise ProtocolError("JSON object must contain a string 'action' field")

    if action_type not in _REQUIRED_FIELDS:
        raise ProtocolError(f"unknown action type: {action_type}")

    keys = set(data.keys())
    unexpected = keys - _SCHEMA_FIELDS
    if unexpected:
        raise ProtocolError(f"unexpected fields for {action_type} action: {sorted(unexpected)}")
    missing = _REQUIRED_FIELDS[action_type] - keys
    if missing:
        raise ProtocolError(f"missing fields for {action_type} action: {sorted(missing)}")

    if action_type == "list_files":
        return ListFiles()

    elif action_type == "read_file":
        return ReadFile(path=relative_path(data["path"]))

    elif action_type == "write_file":
        content = data["content"]
        if not isinstance(content, str):
            raise ProtocolError("write_file requires a string content")
        return WriteFile(path=relative_path(data["path"]), content=content)

    elif action_type == "apply_patch":
        patch = data["patch"]
        if not isinstance(patch, str) or not patch.strip():
            raise ProtocolError("apply_patch requires non-empty string patch")
        return ApplyPatch(patch=patch)

    elif action_type == "run_tests":
        return RunTests()

    else:
        summary = data.get("summary", "")
        if not isinstance(summary, str):
            raise ProtocolError("finish requires a string summary")
        return Finish(summary=summary)


def action_json_schema() -> dict[str, object]:
    return {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": list(_REQUIRED_FIELDS),
            },
            "path": {"type": "string"},
            "content": {"type": "string"},
            "patch": {"type": "string"},
            "summary": {"type": "string"},
        },
        "required": ["action"],
        "additionalProperties": False,
    }
