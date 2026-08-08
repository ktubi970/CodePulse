from pathlib import Path

import pytest

from runner.config import ConfigError, load_config


def test_load_config_returns_fixed_common_budget(tmp_path: Path) -> None:
    path = tmp_path / "codepulse.toml"
    path.write_text(
        """
[ollama]
base_url = "http://127.0.0.1:11434"

[benchmark]
models = ["qwen2.5:1.5b"]
tasks = ["bug_off_by_one"]
result_db = "results/test.sqlite3"
temperature = 0.0
seed = 42
context_tokens = 8192
max_output_tokens = 1024
max_turns = 12
response_timeout_s = 120.0
test_timeout_s = 30.0
run_timeout_s = 1800.0
""",
        encoding="utf-8",
    )

    config = load_config(path)

    assert config.ollama.base_url == "http://127.0.0.1:11434"
    assert config.models == ("qwen2.5:1.5b",)
    assert config.tasks == ("bug_off_by_one",)
    assert config.budget.max_turns == 12
    assert config.result_db == (tmp_path / "results/test.sqlite3").resolve()


def test_load_config_rejects_non_loopback_endpoint(tmp_path: Path) -> None:
    path = tmp_path / "codepulse.toml"
    path.write_text(
        '[ollama]\nbase_url="https://example.com"\n'
        '[benchmark]\nmodels=["m"]\ntasks=["t"]\nresult_db="r.db"\n',
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="loopback"):
        load_config(path)


def test_load_config_rejects_empty_models(tmp_path: Path) -> None:
    path = tmp_path / "codepulse.toml"
    path.write_text(
        '[ollama]\nbase_url="http://127.0.0.1:11434"\n'
        '[benchmark]\nmodels=[]\ntasks=[]\nresult_db="r.db"\n',
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="empty"):
        load_config(path)
