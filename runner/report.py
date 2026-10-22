"""Markdown leaderboard built from the SQLite results, for README files and reports."""
from collections import Counter
import json
import statistics
from typing import Any


def latest_per_pair(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep the newest run of each (model, task) pair; `runs` must be ordered oldest first."""
    latest: dict[tuple[str, str], dict[str, Any]] = {}
    for run in runs:
        latest[(run["model_tag"], run["task_id"])] = run
    return list(latest.values())


def _distinct(runs: list[dict[str, Any]], key: str) -> str:
    return ", ".join(sorted({str(r[key]) for r in runs}))


def _budget_line(runs: list[dict[str, Any]]) -> str:
    parameter_sets = {r["parameters_json"] for r in runs}
    if len(parameter_sets) > 1:
        return f"**Warning:** these runs used {len(parameter_sets)} different parameter sets."
    params = json.loads(parameter_sets.pop())
    return "Budget: " + ", ".join(f"`{key}={value}`" for key, value in sorted(params.items()))


def render_markdown(runs: list[dict[str, Any]]) -> str:
    runs = latest_per_pair(runs)
    if not runs:
        return "No finished runs in this database.\n"

    models = sorted({r["model_tag"] for r in runs})
    tasks = sorted({r["task_id"] for r in runs})
    by_model = {m: [r for r in runs if r["model_tag"] == m] for m in models}

    ranking = sorted(
        models,
        key=lambda m: (
            -sum(r["success"] for r in by_model[m]) / len(by_model[m]),
            statistics.median(r["duration_s"] for r in by_model[m]),
            m,
        ),
    )

    dates = sorted(r["created_at"][:10] for r in runs)
    lines = [
        f"{len(runs)} runs ({len(models)} models x {len(tasks)} tasks, latest run per pair), "
        f"recorded {dates[0]}{'' if dates[0] == dates[-1] else ' to ' + dates[-1]}.",
        "",
        f"Ollama {_distinct(runs, 'ollama_version')} · Python {_distinct(runs, 'python_version')} · "
        f"{_distinct(runs, 'platform_system')}",
        "",
        _budget_line(runs),
        "",
        "| Rank | Model | Solved | Success rate | Median run time |",
        "|---:|---|---:|---:|---:|",
    ]
    for rank, model in enumerate(ranking, start=1):
        model_runs = by_model[model]
        solved = sum(r["success"] for r in model_runs)
        median = statistics.median(r["duration_s"] for r in model_runs)
        lines.append(
            f"| {rank} | `{model}` | {solved}/{len(model_runs)} | {solved / len(model_runs):.0%} | {median:.1f} s |"
        )

    lines += ["", "### Per task", "", "| Task | Solved by |", "|---|---:|"]
    for task in tasks:
        task_runs = [r for r in runs if r["task_id"] == task]
        lines.append(f"| `{task}` | {sum(r['success'] for r in task_runs)}/{len(task_runs)} models |")

    failures = Counter(r["status"] for r in runs if not r["success"])
    if failures:
        lines += ["", "### Failure modes", "", "| Status | Runs |", "|---|---:|"]
        lines += [f"| `{status}` | {count} |" for status, count in failures.most_common()]

    lines += ["", "### Matrix", "", "| Model | " + " | ".join(f"`{t}`" for t in tasks) + " |"]
    lines.append("|---|" + "---:|" * len(tasks))
    for model in ranking:
        cells = {r["task_id"]: ("✅" if r["success"] else "❌") for r in by_model[model]}
        lines.append(f"| `{model}` | " + " | ".join(cells.get(t, "·") for t in tasks) + " |")

    return "\n".join(lines) + "\n"
