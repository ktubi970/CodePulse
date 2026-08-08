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
