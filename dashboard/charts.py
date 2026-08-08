from typing import Any

import plotly.express as px
import plotly.graph_objects as go

from dashboard.data import HeatmapMatrix


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
            text=[f"{r:.1f}% ({c} runs)" for r, c in zip(rates, counts)],
            textposition="auto",
            marker_color="#2b5c8f",
        )
    )

    fig.update_layout(
        title="Model Ranking by Benchmark Success Rate (%)",
        xaxis_title="Success Rate (%)",
        yaxis_title="Model Tag",
        xaxis=dict(range=[0, 105]),
        height=max(300, len(models) * 40),
        margin=dict(l=20, r=20, t=40, b=20),
    )
    return fig


def scatter_figure(rows: list[dict[str, Any]]) -> go.Figure:
    if not rows:
        fig = go.Figure()
        fig.update_layout(title="No data available for scatter plot")
        return fig

    models = [r["model"] for r in rows]
    rates = [r["success_rate"] * 100.0 for r in rows]
    durations = [r["median_duration_s"] for r in rows]

    fig = px.scatter(
        x=durations,
        y=rates,
        text=models,
        labels={"x": "Median Duration (seconds)", "y": "Success Rate (%)"},
        title="Success Rate vs Median Execution Time",
    )

    fig.update_traces(marker=dict(size=14, color="#1f77b4"), textposition="top center")
    fig.update_layout(
        yaxis=dict(range=[-5, 105]),
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
