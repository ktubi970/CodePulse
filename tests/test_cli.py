from pathlib import Path
import pytest

from runner.cli import main


def test_cli_help(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "CodePulse Local" in captured.out


def test_cli_validate_tasks(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # Point to repo root config
    res = main(["--config", "codepulse.toml", "validate-tasks"])
    assert res == 0
    captured = capsys.readouterr()
    assert "Discovered 12 tasks" in captured.out
    assert captured.out.count("reference: passes") == 12


def test_cli_validate_tasks_fails_on_broken_reference(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from tests.test_manifests import write_task

    task = write_task(tmp_path / "tasks")
    (task / "repo" / "tests").mkdir()
    (task / "repo" / "tests" / "test_x.py").write_text("def test_x(): assert False\n", encoding="utf-8")
    (task / "solution").mkdir()  # empty solution: tests still fail
    config = tmp_path / "codepulse.toml"
    config.write_text('[benchmark]\nmodels = ["m"]\n', encoding="utf-8")

    assert main(["--config", str(config), "validate-tasks"]) == 1
    assert "MISSING OR FAILING" in capsys.readouterr().out
