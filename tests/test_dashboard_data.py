from dashboard.data import DashboardRun, heatmap_matrix, ranking_rows, scatter_rows

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


def test_heatmap_preserves_missing_cells() -> None:
    matrix = heatmap_matrix(RUNS)
    assert matrix.models == ("m1", "m2")
    assert matrix.tasks == ("t1", "t2")
    assert matrix.values == ((1.0, 0.0), (1.0, None))
