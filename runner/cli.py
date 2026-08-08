import argparse
from pathlib import Path
import sys
from typing import Sequence

from agent.executor import WorkspaceExecutor
from agent.ollama import OllamaClient
from runner.benchmark import BenchmarkRunner
from runner.config import load_config
from runner.manifests import discover_tasks
from runner.storage import ResultStore


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="codepulse",
        description="CodePulse Local — Offline SLM coding agent benchmark runner.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("codepulse.toml"),
        help="Path to codepulse.toml configuration file.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # list-models
    subparsers.add_parser("list-models", help="List locally installed Ollama models.")

    # validate-tasks
    subparsers.add_parser("validate-tasks", help="Validate task manifests and initial baseline states.")

    # run
    run_parser = subparsers.add_parser("run", help="Run benchmark for a single model and task.")
    run_parser.add_argument("--model", required=True, help="Ollama model tag.")
    run_parser.add_argument("--task", required=True, help="Task ID.")

    # batch
    subparsers.add_parser("batch", help="Run complete benchmark matrix.")

    # show-runs
    show_parser = subparsers.add_parser("show-runs", help="Show past run records from SQLite storage.")
    show_parser.add_argument("--limit", type=int, default=20, help="Maximum number of runs to display.")

    args = parser.parse_args(argv)
    config_path = args.config.resolve()

    try:
        config = load_config(config_path)
    except Exception as err:
        print(f"Configuration error: {err}", file=sys.stderr)
        return 1

    if args.command == "list-models":
        try:
            client = OllamaClient(config.ollama.base_url)
            models = client.list_models()
            print(f"Ollama Version: {client.version()}")
            print(f"{'TAG':<25} {'DIGEST':<15} {'SIZE':<10} {'QUANT':<10}")
            print("-" * 65)
            for m in models:
                print(f"{m.name:<25} {m.digest[:12]:<15} {m.parameter_size:<10} {m.quantization:<10}")
            return 0
        except Exception as err:
            print(f"Error listing models from Ollama: {err}", file=sys.stderr)
            return 1

    elif args.command == "validate-tasks":
        tasks_dir = config_path.parent / "tasks"
        discovered = discover_tasks(tasks_dir)
        print(f"Discovered {len(discovered)} tasks in '{tasks_dir}':")
        for task_id, manifest in discovered.items():
            with WorkspaceExecutor.create(manifest, test_timeout_s=manifest.test_timeout_s) as executor:
                res = executor.final_test()
                status = "FAIL (Expected)" if res.exit_code != 0 else "PASS (UNEXPECTED)"
                print(f" - {task_id:<30} [{manifest.category:<15}] -> Initial test: {status}")
        return 0

    elif args.command == "run":
        try:
            runner = BenchmarkRunner(config=config)
            outcome = runner.run_one(model_tag=args.model, task_id=args.task)
            print(f"\nRun Completed: {outcome.run_id}")
            print(f"Status: {outcome.status}")
            print(f"Success: {outcome.success}")
            print(f"Turns: {outcome.turns}")
            print(f"Duration: {outcome.duration_s:.2f}s")
            return 0 if outcome.success else 1
        except Exception as err:
            print(f"Run error: {err}", file=sys.stderr)
            return 1

    elif args.command == "batch":
        try:
            runner = BenchmarkRunner(config=config)
            outcomes = runner.run_batch()
            passed = sum(1 for o in outcomes if o.success)
            print(f"\nBatch completed: {passed}/{len(outcomes)} passed.")
            return 0
        except Exception as err:
            print(f"Batch error: {err}", file=sys.stderr)
            return 1

    elif args.command == "show-runs":
        try:
            store = ResultStore(config.result_db)
            runs = store.list_runs(limit=args.limit)
            if not runs:
                print("No runs recorded in SQLite database.")
                return 0
            print(f"{'RUN ID':<38} {'MODEL':<20} {'TASK':<25} {'SUCCESS':<10} {'TURNS':<6} {'STATUS':<15}")
            print("-" * 115)
            for r in runs:
                print(
                    f"{r['run_id']:<38} {r['model_tag']:<20} {r['task_id']:<25} "
                    f"{'YES' if r['success'] else 'NO':<10} {r['turns']:<6} {r['status']:<15}"
                )
            return 0
        except Exception as err:
            print(f"Error reading runs: {err}", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
