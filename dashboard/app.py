import os
from pathlib import Path
import streamlit as st

from dashboard.charts import heatmap_figure, ranking_figure, scatter_figure
from dashboard.data import (
    heatmap_matrix,
    latest_per_pair,
    load_demo_runs,
    load_sqlite_runs,
    ranking_rows,
    scatter_rows,
)

st.set_page_config(page_title="CodePulse Local — Benchmark Dashboard", layout="wide")

st.title("CodePulse Local — Benchmark Dashboard")

# Scope warning header on every view
st.warning(
    "These results only hold for this task corpus, this hardware, these Ollama and model builds, "
    "and these parameters. They are not a general ranking of model quality."
)

demo_env = os.environ.get("CODEPULSE_DEMO", "").strip() in ("1", "true", "TRUE")

st.sidebar.header("Data source")
use_demo = st.sidebar.checkbox("Demo mode (fictional data)", value=demo_env)

default_db_path = Path("results/codepulse.sqlite3")
db_input = st.sidebar.text_input("Local SQLite database", value=str(default_db_path))
latest_only = st.sidebar.checkbox(
    "Latest run per model and task",
    value=True,
    help="Re-runs replace earlier results instead of being averaged with them.",
)

if use_demo:
    st.info("💡 Demo mode: the results shown are fictional (examples/demo_results.jsonl).")
    demo_file = Path("examples/demo_results.jsonl")
    try:
        runs = load_demo_runs(demo_file)
    except Exception as err:
        st.error(f"Could not load demo data: {err}")
        runs = []
else:
    db_path = Path(db_input)
    if not db_path.exists():
        st.info(f"No SQLite database found at '{db_path}'. Run a benchmark with the CLI to produce results.")
        runs = []
    else:
        try:
            runs = load_sqlite_runs(db_path)
        except Exception as err:
            st.error(f"Could not read the SQLite database: {err}")
            runs = []

if latest_only:
    runs = latest_per_pair(runs)

if not runs:
    st.warning("No benchmark results to display.")
else:
    st.markdown(f"**Runs analysed:** `{len(runs)}`")

    col1, col2 = st.columns(2)
    with col1:
        rank_data = ranking_rows(runs)
        st.plotly_chart(ranking_figure(rank_data), use_container_width=True)

    with col2:
        scat_data = scatter_rows(runs)
        st.plotly_chart(scatter_figure(scat_data), use_container_width=True)

    st.subheader("Pass/fail matrix")
    hm_matrix = heatmap_matrix(runs)
    st.plotly_chart(heatmap_figure(hm_matrix), use_container_width=True)

    st.divider()
    st.subheader("Run details")

    run_options = {f"{r.model_tag} | {r.task_id} | {r.run_id[:8]} ({r.status})": r for r in runs}
    selected_label = st.selectbox("Select a run", list(run_options.keys()))

    if selected_label:
        sel_run = run_options[selected_label]

        t_meta, t_inst, t_actions, t_patch, t_test = st.tabs(
            ["Metadata", "Instruction", "Actions", "Final patch", "Pytest evidence"]
        )

        with t_meta:
            st.json(
                {
                    "run_id": sel_run.run_id,
                    "model_tag": sel_run.model_tag,
                    "task_id": sel_run.task_id,
                    "success": sel_run.success,
                    "status": sel_run.status,
                    "turns": sel_run.turns,
                    "duration_s": sel_run.duration_s,
                    "is_demo": sel_run.is_demo,
                }
            )

        with t_inst:
            st.markdown(sel_run.instruction or "No instruction recorded.")

        with t_actions:
            if sel_run.actions:
                st.json(list(sel_run.actions))
            else:
                st.write("No actions recorded.")

        with t_patch:
            if sel_run.final_patch:
                st.code(sel_run.final_patch, language="diff")
            else:
                st.write("No patch produced.")

        with t_test:
            st.markdown("#### Pytest stdout")
            st.code(sel_run.final_test_stdout or "Empty", language="text")
            st.markdown("#### Pytest stderr")
            st.code(sel_run.final_test_stderr or "Empty", language="text")
