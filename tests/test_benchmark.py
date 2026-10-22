from pathlib import Path
import pytest

from agent.executor import ExecutorError
from agent.ollama import ModelMissing, OllamaModel, OllamaReply
from runner.benchmark import BenchmarkRunner
from runner.config import load_config


class FakeOllamaClient:
    def __init__(self, models: list[str] | None = None) -> None:
        self.models_list = models if models is not None else ["qwen2.5:1.5b"]

    def version(self) -> str:
        return "0.test"

    def list_models(self) -> list[OllamaModel]:
        return [OllamaModel(m, "digest", "1B", "Q4") for m in self.models_list]

    def require_model(self, tag: str) -> OllamaModel:
        if tag in self.models_list:
            return OllamaModel(tag, "digest", "1B", "Q4")
        raise ModelMissing(f"Tag {tag} missing")

    def chat(self, **kwargs: object) -> OllamaReply:
        return OllamaReply(
            content='{"action":"finish","summary":"ok"}',
            prompt_tokens=10,
            completion_tokens=5,
            total_duration_ns=1000,
        )


def test_runner_refuses_to_start_without_test_runtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken_runtime() -> str:
        raise ExecutorError("cannot import pytest")

    monkeypatch.setattr("runner.benchmark.check_test_runtime", broken_runtime)
    cfg_file = tmp_path / "codepulse.toml"
    cfg_file.write_text('[benchmark]\nmodels=["m"]\nresult_db="db.sqlite3"\n', encoding="utf-8")
    with pytest.raises(ExecutorError, match="cannot import"):
        BenchmarkRunner(config=load_config(cfg_file), client=FakeOllamaClient())


def test_runner_rejects_missing_model_before_creating_run(tmp_path: Path) -> None:
    cfg_file = tmp_path / "codepulse.toml"
    cfg_file.write_text(
        '[ollama]\nbase_url="http://127.0.0.1:11434"\n[benchmark]\nmodels=["m"]\ntasks=["bug_off_by_one"]\nresult_db="db.sqlite3"\n',
        encoding="utf-8",
    )
    config = load_config(cfg_file)
    fake_client = FakeOllamaClient(models=[])
    runner = BenchmarkRunner(config=config, client=fake_client)
    with pytest.raises(ModelMissing):
        runner.run_one("missing:test", "bug_off_by_one")
