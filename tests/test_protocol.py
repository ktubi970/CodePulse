import json

import pytest

from agent.protocol import (
    ApplyPatch,
    Finish,
    ListFiles,
    ProtocolError,
    ReadFile,
    RunTests,
    WriteFile,
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


def test_parse_write_file_action() -> None:
    raw = json.dumps({"action": "write_file", "path": "src/a.py", "content": "x = 2\n"})
    assert parse_action(raw) == WriteFile(path="src/a.py", content="x = 2\n")


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
        ('{"action":"read_file"}', "missing"),
        ('{"action":"write_file","path":"src/a.py"}', "missing"),
        ('{"action":"write_file","path":"../a.py","content":""}', "traverse"),
    ],
)
def test_parse_action_fails_closed(raw: str, message: str) -> None:
    with pytest.raises(ProtocolError, match=message):
        parse_action(raw)


def test_schema_exposes_only_six_actions() -> None:
    schema = action_json_schema()
    assert schema["properties"]["action"]["enum"] == [
        "list_files",
        "read_file",
        "write_file",
        "apply_patch",
        "run_tests",
        "finish",
    ]


# Replies seen in real runs: valid under the schema sent to Ollama, yet rejected by the old parser.
@pytest.mark.parametrize(
    "raw,expected",
    [
        ('{"action":"list_files","path":"."}', ListFiles()),
        ('{"action":"read_file","path":"src/a.py","summary":"look"}', ReadFile(path="src/a.py")),
        ('{"action":"apply_patch","patch":"--- a/a.py","summary":"fix"}', ApplyPatch(patch="--- a/a.py")),
        ('{"action":"finish"}', Finish(summary="")),
    ],
)
def test_parser_ignores_schema_fields_unused_by_the_action(raw: str, expected: object) -> None:
    assert parse_action(raw) == expected


def test_every_schema_property_is_accepted_by_every_action() -> None:
    schema = action_json_schema()
    filler = {"path": "src/a.py", "patch": "--- a/a.py", "content": "x = 1\n", "summary": "s"}
    assert set(schema["properties"]) == {"action", *filler}
    for action in schema["properties"]["action"]["enum"]:
        parse_action(json.dumps({"action": action, **filler}))
