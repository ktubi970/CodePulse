import argparse
from pathlib import Path
import sys
from typing import Sequence

from agent.executor import WorkspaceExecutor, check_test_runtime
from agent.ollama import OllamaClient
from runner.benchmark import BenchmarkRunner
from runner.config import load_config
from runner.manifests import discover_tasks
from runner.report import render_markdown
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

    # report
    report_parser = subparsers.add_parser("report", help="Write a Markdown leaderboard of the latest runs.")
    report_parser.add_argument("--db", type=Path, help="SQLite results database (default: result_db from config).")
    report_parser.add_argument("--output", type=Path, help="Write to this file instead of standard output.")

    args = parser.parse_args(argv)
    config_path = args.config.resolve()

    try:
        config = load_config(config_path)
    except Exception as err:
        print(f"Configuration error: {err}", file=sys.stderr)
        return 1

    if args.command == "list-models":
        try:
            client = OllamaClient(config.ollama.base_url, timeout_seconds=config.budget.response_timeout_s)
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
        try:
            print(f"Test runtime: {check_test_runtime()}")
        except Exception as err:
            print(f"Test runtime error: {err}", file=sys.stderr)
            return 1
        discovered = discover_tasks(config.tasks_dir)
        print(f"Discovered {len(discovered)} tasks in '{config.tasks_dir}':")
        problems = 0
        for task_id, manifest in discovered.items():
            with WorkspaceExecutor.create(manifest, test_timeout_s=manifest.test_timeout_s) as executor:
                initial_ok = executor.final_test().exit_code != 0
            if manifest.solution_path is None:
                solution_ok = False
            else:
                with WorkspaceExecutor.create(manifest, test_timeout_s=manifest.test_timeout_s) as executor:
                    executor.overlay(manifest.solution_path)
                    solution_ok = executor.final_test().passed and not executor.surviving_mutants()
            problems += (not initial_ok) + (not solution_ok)
            initial = "fails (expected)" if initial_ok else "PASSES (UNEXPECTED)"
            solution = "passes" if solution_ok else "MISSING OR FAILING"
            print(f" - {task_id:<30} [{manifest.category:<15}] initial: {initial:<19} reference: {solution}")
        if problems:
            print(f"{problems} task problem(s) found.", file=sys.stderr)
            return 1
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

    elif args.command == "report":
        db_path = args.db or config.result_db
        if not db_path.is_file():
            print(f"No results database at {db_path}", file=sys.stderr)
            return 1
        report = render_markdown(ResultStore(db_path).finished_runs())
        if args.output:
            args.output.write_text(report, encoding="utf-8")
            print(f"Report written to {args.output}")
        else:
            sys.stdout.reconfigure(encoding="utf-8")  # the matrix uses emoji
            print(report, end="")
        return 0

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
