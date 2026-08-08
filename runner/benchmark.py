from pathlib import Path
from typing import Any

from agent.loop import RunOutcome, run_agent
from agent.ollama import OllamaClient, OllamaModel
from runner.config import AppConfig, load_config
from runner.manifests import TaskManifest, discover_tasks
from runner.storage import ResultStore


class BenchmarkRunner:
    def __init__(self, config: AppConfig, client: Any | None = None) -> None:
        self.config = config
        self.store = ResultStore(config.result_db)
        self.client = client if client is not None else OllamaClient(config.ollama.base_url)

        # Discover tasks
        tasks_root = (config.result_db.parent.parent / "tasks").resolve()
        if not tasks_root.is_dir():
            tasks_root = Path("tasks").resolve()

        self.discovered_tasks = discover_tasks(tasks_root)
        self.ollama_version = "unknown"
        try:
            self.ollama_version = self.client.version()
        except Exception:
            pass

    def run_one(self, model_tag: str, task_id: str, is_demo: bool = False) -> RunOutcome:
        if task_id not in self.discovered_tasks:
            raise ValueError(f"Task ID '{task_id}' is not in discovered tasks")

        manifest = self.discovered_tasks[task_id]

        # Require installed model tag (or fallback mock)
        if hasattr(self.client, "require_model"):
            model = self.client.require_model(model_tag)
        else:
            model = OllamaModel(name=model_tag, digest="mock", parameter_size="1B", quantization="Q4")

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
                except Exception as err:
                    print(f"[{model_tag}] [{task_id}] -> ERROR: {err}")

        return outcomes
