from typing import Any

from agent.executor import check_test_runtime
from agent.loop import RunOutcome, run_agent
from agent.ollama import OllamaClient, OllamaUnavailable
from runner.config import AppConfig
from runner.manifests import discover_tasks
from runner.storage import ResultStore


class BenchmarkRunner:
    def __init__(self, config: AppConfig, client: Any | None = None) -> None:
        check_test_runtime()
        self.config = config
        self.store = ResultStore(config.result_db)
        self.client = (
            client
            if client is not None
            else OllamaClient(config.ollama.base_url, timeout_seconds=config.budget.response_timeout_s)
        )
        self.discovered_tasks = discover_tasks(config.tasks_dir)
        self.ollama_version = "unknown"
        try:
            self.ollama_version = self.client.version()
        except Exception:
            pass

    def run_one(self, model_tag: str, task_id: str, is_demo: bool = False) -> RunOutcome:
        if task_id not in self.discovered_tasks:
            raise ValueError(f"Task ID '{task_id}' is not in discovered tasks")

        manifest = self.discovered_tasks[task_id]

        model = self.client.require_model(model_tag)
        # Load weights now so model start-up time is not charged to the first timed turn.
        self.client.load_model(model.name)

        return run_agent(
            client=self.client,
            model=model,
            ollama_version=self.ollama_version,
            manifest=manifest,
            budget=self.config.budget,
            store=self.store,
            is_demo=is_demo,
        )

    def run_batch(self) -> list[RunOutcome]:
        selected_tasks = self.config.tasks if self.config.tasks else tuple(sorted(self.discovered_tasks.keys()))
        selected_models = self.config.models

        outcomes: list[RunOutcome] = []

        for model_tag in selected_models:
            for task_id in selected_tasks:
                try:
                    outcome = self.run_one(model_tag=model_tag, task_id=task_id)
                    outcomes.append(outcome)
                    status_symbol = "PASSED" if outcome.success else f"FAILED ({outcome.status})"
                    print(f"[{model_tag}] [{task_id}] -> {status_symbol} ({outcome.duration_s:.2f}s)")
                except KeyboardInterrupt:
                    print("\nBatch execution cancelled by user.")
                    raise
                except OllamaUnavailable as err:
                    # Every remaining run would fail the same way; stop instead of recording noise.
                    print(f"[{model_tag}] [{task_id}] -> Ollama unavailable, stopping batch: {err}")
                    raise
                except Exception as err:
                    print(f"[{model_tag}] [{task_id}] -> ERROR: {err}")

        return outcomes
