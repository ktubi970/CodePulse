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
    if not isinstance(value, str) or not value.strip():
        raise ProtocolError("path must be a non-empty relative path")
    path_str = value.replace("\\", "/").strip()
    path = PurePosixPath(path_str)
    if path.is_absolute() or ".." in path.parts:
        raise ProtocolError("path must be relative and cannot traverse parents")
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

    keys = set(data.keys())

    if action_type == "list_files":
        if keys != {"action"}:
            raise ProtocolError(f"unexpected fields for list_files action: {keys - {'action'}}")
        return ListFiles()

    elif action_type == "read_file":
        if keys != {"action", "path"}:
            raise ProtocolError(f"unexpected or missing fields for read_file action: {keys}")
        path = _relative_path(data["path"])
        return ReadFile(path=path)

    elif action_type == "apply_patch":
        if keys != {"action", "patch"}:
            raise ProtocolError(f"unexpected or missing fields for apply_patch action: {keys}")
        patch = data["patch"]
        if not isinstance(patch, str) or not patch.strip():
            raise ProtocolError("apply_patch requires non-empty string patch")
        return ApplyPatch(patch=patch)

    elif action_type == "run_tests":
        if keys != {"action"}:
            raise ProtocolError(f"unexpected fields for run_tests action: {keys - {'action'}}")
        return RunTests()

    elif action_type == "finish":
        if keys != {"action", "summary"}:
            raise ProtocolError(f"unexpected or missing fields for finish action: {keys}")
        summary = data["summary"]
        if not isinstance(summary, str):
            raise ProtocolError("finish requires a string summary")
        return Finish(summary=summary)

    else:
        raise ProtocolError(f"unknown action type: {action_type}")


def action_json_schema() -> dict[str, object]:
    return {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list_files", "read_file", "apply_patch", "run_tests", "finish"],
            },
            "path": {"type": "string"},
            "patch": {"type": "string"},
            "summary": {"type": "string"},
        },
        "required": ["action"],
        "additionalProperties": False,
    }
