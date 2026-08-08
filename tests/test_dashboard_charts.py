from dashboard.charts import heatmap_figure, ranking_figure, scatter_figure
from dashboard.data import HeatmapMatrix


def test_chart_builders_produce_plotly_figures() -> None:
    rows = [{"model": "m1", "success_rate": 0.5, "runs": 2, "median_duration_s": 3.0}]
    matrix = HeatmapMatrix(models=("m1",), tasks=("t1",), values=((0.5,),))

    r_fig = ranking_figure(rows)
    s_fig = scatter_figure(rows)
    h_fig = heatmap_figure(matrix)

    assert r_fig is not None
    assert s_fig is not None
    assert h_fig is not None
