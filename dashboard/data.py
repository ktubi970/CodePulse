from contextlib import closing
from dataclasses import dataclass
import json
from pathlib import Path
import sqlite3
import statistics
from typing import Any


class DashboardDataError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class DashboardRun:
    run_id: str
    model_tag: str
    task_id: str
    success: bool
    duration_s: float
    is_demo: bool
    turns: int = 0
    status: str = "success"
    final_patch: str = ""
    instruction: str = ""
    final_test_stdout: str = ""
    final_test_stderr: str = ""
    actions: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True, slots=True)
class HeatmapMatrix:
    models: tuple[str, ...]
    tasks: tuple[str, ...]
    values: tuple[tuple[float | None, ...], ...]


def load_sqlite_runs(db_path: Path) -> list[DashboardRun]:
    path = db_path.resolve()
    if not path.is_file():
        return []

    with closing(sqlite3.connect(path)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM runs WHERE status != 'running' ORDER BY created_at ASC").fetchall()
        actions_by_run: dict[str, list[dict[str, Any]]] = {}
        for a in conn.execute("SELECT * FROM actions ORDER BY run_id, turn ASC"):
            actions_by_run.setdefault(a["run_id"], []).append(dict(a))

    runs = []
    for r in rows:
        run_id = r["run_id"]
        actions = tuple(actions_by_run.get(run_id, []))

        runs.append(
            DashboardRun(
                run_id=run_id,
                model_tag=r["model_tag"],
                task_id=r["task_id"],
                success=bool(r["success"]),
                duration_s=float(r["duration_s"] or 0.0),
                is_demo=bool(r["is_demo"]),
                turns=int(r["turns"] or 0),
                status=r["status"] or "unknown",
                final_patch=r["final_patch"] or "",
                instruction=r["instruction"] or "",
                final_test_stdout=r["final_test_stdout"] or "",
                final_test_stderr=r["final_test_stderr"] or "",
                actions=actions,
            )
        )

    return runs


def load_demo_runs(jsonl_path: Path) -> list[DashboardRun]:
    path = jsonl_path.resolve()
    if not path.is_file():
        raise DashboardDataError(f"Demo results file missing at: {path}")

    runs = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except Exception as err:
            raise DashboardDataError(f"Invalid JSON in demo results: {err}") from err

        if not data.get("is_demo"):
            raise DashboardDataError("Demo run must have 'is_demo: true'")

        runs.append(
            DashboardRun(
                run_id=data.get("run_id", "demo"),
                model_tag=data.get("model_tag", "demo_model"),
                task_id=data.get("task_id", "demo_task"),
                success=bool(data.get("success", False)),
                duration_s=float(data.get("duration_s", 0.0)),
                is_demo=True,
                turns=int(data.get("turns", 0)),
                status=data.get("status", "success"),
                final_patch=data.get("final_patch", ""),
                instruction=data.get("instruction", ""),
                final_test_stdout=data.get("final_test_stdout", ""),
                final_test_stderr=data.get("final_test_stderr", ""),
                actions=tuple(data.get("actions", [])),
            )
        )

    return runs


def latest_per_pair(runs: list[DashboardRun]) -> list[DashboardRun]:
    """Keep the newest run of each (model, task) pair; `runs` must be ordered oldest first."""
    seen: set[tuple[str, str]] = set()
    latest: list[DashboardRun] = []
    for r in reversed(runs):
        if (r.model_tag, r.task_id) not in seen:
            seen.add((r.model_tag, r.task_id))
            latest.append(r)
    return latest[::-1]


def ranking_rows(runs: list[DashboardRun]) -> list[dict[str, Any]]:
    if not runs:
        return []

    groups: dict[str, list[DashboardRun]] = {}
    for r in runs:
        groups.setdefault(r.model_tag, []).append(r)

    results = []
    for model_tag, model_runs in groups.items():
        total = len(model_runs)
        passed = sum(1 for r in model_runs if r.success)
        rate = passed / total if total > 0 else 0.0
        results.append({"model": model_tag, "success_rate": rate, "runs": total})

    # Sort descending by success_rate, then model_tag
    results.sort(key=lambda x: (-x["success_rate"], x["model"]))
    return results


def scatter_rows(runs: list[DashboardRun]) -> list[dict[str, Any]]:
    if not runs:
        return []

    groups: dict[str, list[DashboardRun]] = {}
    for r in runs:
        groups.setdefault(r.model_tag, []).append(r)

    results = []
    for model_tag, model_runs in groups.items():
        total = len(model_runs)
        passed = sum(1 for r in model_runs if r.success)
        rate = passed / total if total > 0 else 0.0
        durations = [r.duration_s for r in model_runs]
        med_dur = statistics.median(durations) if durations else 0.0
        results.append(
            {
                "model": model_tag,
                "success_rate": rate,
                "median_duration_s": float(med_dur),
            }
        )

    results.sort(key=lambda x: x["model"])
    return results


def heatmap_matrix(runs: list[DashboardRun]) -> HeatmapMatrix:
    models = sorted(list({r.model_tag for r in runs}))
    tasks = sorted(list({r.task_id for r in runs}))

    lookup: dict[tuple[str, str], list[DashboardRun]] = {}
    for r in runs:
        lookup.setdefault((r.model_tag, r.task_id), []).append(r)

    matrix_rows = []
    for m in models:
        row_vals: list[float | None] = []
        for t in tasks:
            pair_runs = lookup.get((m, t))
            if not pair_runs:
                row_vals.append(None)
            else:
                passed = sum(1 for r in pair_runs if r.success)
                row_vals.append(passed / len(pair_runs))
        matrix_rows.append(tuple(row_vals))

    return HeatmapMatrix(models=tuple(models), tasks=tuple(tasks), values=tuple(matrix_rows))
