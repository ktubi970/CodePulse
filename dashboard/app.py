import os
from pathlib import Path
import streamlit as st

from dashboard.charts import heatmap_figure, ranking_figure, scatter_figure
from dashboard.data import (
    load_demo_runs,
    load_sqlite_runs,
    heatmap_matrix,
    ranking_rows,
    scatter_rows,
)

st.set_page_config(page_title="CodePulse Local — Benchmark Dashboard", layout="wide")

st.title("CodePulse Local — Benchmark Dashboard")

# Scope warning header on every view
st.warning(
    "Ces résultats ne valent que pour ce corpus, ce matériel, cette version d'Ollama et des modèles, "
    "et ces paramètres. Ils ne constituent pas un classement général de qualité."
)

demo_env = os.environ.get("CODEPULSE_DEMO", "").strip() in ("1", "true", "TRUE")

st.sidebar.header("Configuration & Source")
use_demo = st.sidebar.checkbox("Mode Démonstration (Données Fictives)", value=demo_env)

default_db_path = Path("results/codepulse.sqlite3")
db_input = st.sidebar.text_input("Chemin SQLite Local", value=str(default_db_path))

if use_demo:
    st.info("💡 Mode Démonstration actif. Les résultats affichés sont fictifs (examples/demo_results.jsonl).")
    demo_file = Path("examples/demo_results.jsonl")
    try:
        runs = load_demo_runs(demo_file)
    except Exception as err:
        st.error(f"Erreur de chargement des données démo: {err}")
        runs = []
else:
    db_path = Path(db_input)
    if not db_path.exists():
        st.info(f"Aucune base de données SQLite trouvée à '{db_path}'. Exécutez un benchmark via la CLI pour générer des résultats.")
        runs = []
    else:
        try:
            runs = load_sqlite_runs(db_path)
        except Exception as err:
            st.error(f"Erreur d'accès à la base SQLite: {err}")
            runs = []

if not runs:
    st.warning("Aucun résultat de benchmark à afficher.")
else:
    st.markdown(f"**Total de runs analysés :** `{len(runs)}`")

    col1, col2 = st.columns(2)
    with col1:
        rank_data = ranking_rows(runs)
        st.plotly_chart(ranking_figure(rank_data), use_container_width=True)

    with col2:
        scat_data = scatter_rows(runs)
        st.plotly_chart(scatter_figure(scat_data), use_container_width=True)

    st.subheader("Matrice de Performance (Heatmap)")
    hm_matrix = heatmap_matrix(runs)
    st.plotly_chart(heatmap_figure(hm_matrix), use_container_width=True)

    st.divider()
    st.subheader("Détails d'une Exécution (Run Detail)")

    run_options = {f"{r.model_tag} | {r.task_id} | {r.run_id[:8]} ({r.status})": r for r in runs}
    selected_label = st.selectbox("Sélectionner un Run", list(run_options.keys()))

    if selected_label:
        sel_run = run_options[selected_label]

        t_meta, t_inst, t_actions, t_patch, t_test = st.tabs(
            ["Métadonnées", "Instruction", "Actions", "Patch Final", "Preuve Pytest"]
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
            st.markdown(sel_run.instruction or "Aucune instruction enregistrée.")

        with t_actions:
            if sel_run.actions:
                st.json(list(sel_run.actions))
            else:
                st.write("Aucune action enregistrée.")

        with t_patch:
            if sel_run.final_patch:
                st.code(sel_run.final_patch, language="diff")
            else:
                st.write("Aucun patch généré.")

        with t_test:
            st.markdown("#### Stdout Pytest")
            st.code(sel_run.final_test_stdout or "Vide", language="text")
            st.markdown("#### Stderr Pytest")
            st.code(sel_run.final_test_stderr or "Vide", language="text")
