from typing import Any

from plotly.colors import qualitative
import plotly.graph_objects as go

from dashboard.data import HeatmapMatrix

# 24 distinct colours: Plotly's default cycle repeats after 10 models.
PALETTE = qualitative.Dark24


def ranking_figure(rows: list[dict[str, Any]]) -> go.Figure:
    if not rows:
        fig = go.Figure()
        fig.update_layout(title="No data available for ranking")
        return fig

    models = [r["model"] for r in rows]
    rates = [r["success_rate"] * 100.0 for r in rows]
    counts = [r["runs"] for r in rows]

    fig = go.Figure(
        go.Bar(
            x=rates,
            y=models,
            orientation="h",
            text=[f"{r:.1f}% ({c} runs)" for r, c in zip(rates, counts, strict=True)],
            textposition="outside",  # keeps 0% rows labelled
            cliponaxis=False,
            marker_color="#2b5c8f",
        )
    )

    fig.update_layout(
        title="Model Ranking by Benchmark Success Rate (%)",
        xaxis_title="Success Rate (%)",
        yaxis_title="Model Tag",
        xaxis=dict(range=[0, 125]),
        height=max(300, len(models) * 40),
        margin=dict(l=20, r=20, t=40, b=20),
    )
    return fig


def scatter_figure(rows: list[dict[str, Any]]) -> go.Figure:
    if not rows:
        fig = go.Figure()
        fig.update_layout(title="No data available for scatter plot")
        return fig

    # One trace per model with a legend: text labels overlap once there are a dozen models.
    fig = go.Figure(
        [
            go.Scatter(
                x=[r["median_duration_s"]],
                y=[r["success_rate"] * 100.0],
                mode="markers",
                name=r["model"],
                marker=dict(size=13, color=PALETTE[i % len(PALETTE)]),
                hovertemplate=f"{r['model']}<br>%{{y:.0f}}% solved<br>median %{{x:.1f}} s<extra></extra>",
            )
            for i, r in enumerate(rows)
        ]
    )
    fig.update_layout(
        title="Success Rate vs Median Execution Time",
        xaxis_title="Median Duration (seconds)",
        yaxis_title="Success Rate (%)",
        yaxis=dict(range=[-5, 105]),
        legend=dict(title="Model", font=dict(size=11)),
        margin=dict(l=20, r=20, t=40, b=20),
    )
    return fig


def heatmap_figure(matrix: HeatmapMatrix) -> go.Figure:
    if not matrix.models or not matrix.tasks:
        fig = go.Figure()
        fig.update_layout(title="No data available for heatmap")
        return fig

    # Prepare values as percentages or None
    z_vals = []
    text_vals = []

    for row in matrix.values:
        z_row = []
        t_row = []
        for val in row:
            if val is None:
                z_row.append(None)
                t_row.append("N/A")
            else:
                pct = val * 100.0
                z_row.append(pct)
                t_row.append(f"{pct:.0f}%")
        z_vals.append(z_row)
        text_vals.append(t_row)

    fig = go.Figure(
        data=go.Heatmap(
            z=z_vals,
            x=matrix.tasks,
            y=matrix.models,
            text=text_vals,
            texttemplate="%{text}",
            colorscale="Viridis",
            zmin=0,
            zmax=100,
            showscale=True,
        )
    )

    fig.update_layout(
        title="Model Performance Heatmap by Task (Pass %)",
        xaxis_title="Task ID",
        yaxis_title="Model Tag",
        margin=dict(l=20, r=20, t=40, b=20),
    )
    return fig
