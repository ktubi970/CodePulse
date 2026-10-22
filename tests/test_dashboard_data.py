from dashboard.data import DashboardRun, heatmap_matrix, latest_per_pair, ranking_rows, scatter_rows

RUNS = [
    DashboardRun("r1", "m1", "t1", True, 2.0, False),
    DashboardRun("r2", "m1", "t2", False, 6.0, False),
    DashboardRun("r3", "m2", "t1", True, 4.0, False),
]


def test_ranking_uses_success_rate_and_run_count() -> None:
    assert ranking_rows(RUNS) == [
        {"model": "m2", "success_rate": 1.0, "runs": 1},
        {"model": "m1", "success_rate": 0.5, "runs": 2},
    ]


def test_scatter_uses_median_duration() -> None:
    assert scatter_rows(RUNS) == [
        {"model": "m1", "success_rate": 0.5, "median_duration_s": 4.0},
        {"model": "m2", "success_rate": 1.0, "median_duration_s": 4.0},
    ]


def test_latest_per_pair_keeps_only_the_newest_run() -> None:
    # Runs are loaded oldest first; a re-run must replace, not dilute, the earlier result.
    rerun = DashboardRun("r4", "m1", "t2", True, 3.0, False)
    latest = latest_per_pair([*RUNS, rerun])
    assert [r.run_id for r in latest] == ["r1", "r3", "r4"]


def test_heatmap_preserves_missing_cells() -> None:
    matrix = heatmap_matrix(RUNS)
    assert matrix.models == ("m1", "m2")
    assert matrix.tasks == ("t1", "t2")
    assert matrix.values == ((1.0, 0.0), (1.0, None))
