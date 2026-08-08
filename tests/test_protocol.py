import json

import pytest

from agent.protocol import (
    ApplyPatch,
    Finish,
    ListFiles,
    ProtocolError,
    ReadFile,
    RunTests,
    action_json_schema,
    parse_action,
)


def test_parse_list_files_action() -> None:
    assert parse_action('{"action":"list_files"}') == ListFiles()


def test_parse_read_file_action() -> None:
    assert parse_action('{"action":"read_file","path":"src/calc.py"}') == ReadFile(
        path="src/calc.py"
    )


def test_parse_patch_preserves_unified_diff() -> None:
    patch = "--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-x = 1\n+x = 2\n"
    action = parse_action(json.dumps({"action": "apply_patch", "patch": patch}))
    assert action == ApplyPatch(patch=patch)


def test_parse_run_tests_action() -> None:
    assert parse_action('{"action":"run_tests"}') == RunTests()


def test_parse_finish_action() -> None:
    assert parse_action('{"action":"finish","summary":"done"}') == Finish(summary="done")


@pytest.mark.parametrize(
    "raw,message",
    [
        ("not-json", "JSON"),
        ('{"action":"shell","command":"dir"}', "unknown action"),
        ('{"action":"read_file","path":"../secret"}', "traverse"),
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
