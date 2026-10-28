"""Demo local do experimento 001. Não chama modelo."""

import json
from pathlib import Path

import streamlit as st

from prompt_lab.experiment import score_experiment

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT / "experiments"


st.set_page_config(page_title="Prompt Lab", layout="wide")
st.title("Prompt Lab")
st.caption("Eval de geração de SQL. As notas vêm de outputs/ commitados, sem chamada de modelo.")

if not EXPERIMENTS.is_dir():
    st.error(f"Não achei a pasta de experimentos em {EXPERIMENTS}.")
    st.stop()

names = sorted(path.name for path in EXPERIMENTS.iterdir() if (path / "inputs.yaml").is_file())
if not names:
    st.warning("Nenhum experimento com inputs.yaml.")
    st.stop()

chosen = st.selectbox("Experimento", names)
experiment = EXPERIMENTS / chosen
readme = experiment / "README.md"
if readme.is_file():
    with st.expander("Notas do experimento", expanded=False):
        st.markdown(readme.read_text(encoding="utf-8"))

results_path = experiment / "results.json"
if results_path.is_file():
    saved = json.loads(results_path.read_text(encoding="utf-8"))
    bits = []
    if saved.get("model"):
        bits.append(f"modelo `{saved['model']}`")
    if saved.get("source"):
        bits.append(f"source `{saved['source']}`")
    if "cost_usd" in saved:
        bits.append(f"custo USD `{saved['cost_usd']}`")
    if bits:
        st.caption(" · ".join(bits))

try:
    summary = score_experiment(experiment)
except (OSError, ValueError, KeyError) as exc:
    st.error(f"Não consegui pontuar este experimento: {exc}")
    st.stop()

versions = list(summary["metrics"])
metric_rows = [{"version": version, **values} for version, values in summary["metrics"].items()]
st.subheader("Acurácia")
st.dataframe(metric_rows, hide_index=True, width="stretch")

cases = sorted({item["id"] for item in summary["cases"]})
case_id = st.selectbox("Caso", cases)
version = st.radio("Versão do prompt", versions, horizontal=True)
match = next(item for item in summary["cases"] if item["id"] == case_id and item["version"] == version)

left, right = st.columns(2)
with left:
    st.subheader("Prompt")
    if match["rendered"]["system"]:
        st.markdown("**System**")
        st.code(match["rendered"]["system"], language="markdown")
    st.markdown("**Usuário**")
    st.code(match["rendered"]["prompt"], language="markdown")
with right:
    st.subheader("Saída registrada")
    st.code(match["output"] or "(ausente)", language="json" if match["json_ok"] else "text")
    passed = match["json_ok"] and match["rows_match"]
    status = "passou" if passed else "falhou"
    st.markdown(
        f"**{status}.** JSON válido: `{match['json_ok']}`. "
        f"SQL extraído: `{match['sql_extracted']}`. "
        f"Linhas corretas: `{match['rows_match']}`."
    )
    if match["error"]:
        st.warning(match["error"])
