"""Demo local dos experimentos. Não chama modelo."""

from __future__ import annotations

import difflib
import json
from pathlib import Path

import streamlit as st

from prompt_lab.common import load_yaml_mapping
from prompt_lab.experiment import score_path

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT / "experiments"


st.set_page_config(page_title="Prompt Lab", layout="wide")
st.title("Prompt Lab")
st.caption("Eval de prompts para dados. As notas vêm de outputs/ commitados, sem chamada de modelo.")

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
saved: dict = {}
if results_path.is_file():
    try:
        saved = json.loads(results_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        saved = {}
    bits = []
    if saved.get("model"):
        bits.append(f"modelo `{saved['model']}`")
    if saved.get("source"):
        bits.append(f"source `{saved['source']}`")

    p_tok = saved.get("prompt_tokens")
    c_tok = saved.get("completion_tokens")
    if p_tok is None and c_tok is None and "cases" in saved:
        case_items = saved.get("cases", [])
        if any("prompt_tokens" in c or "completion_tokens" in c for c in case_items):
            p_tok = sum(int(c.get("prompt_tokens") or 0) for c in case_items)
            c_tok = sum(int(c.get("completion_tokens") or 0) for c in case_items)

    if p_tok is not None or c_tok is not None:
        total_tokens = (p_tok or 0) + (c_tok or 0)
        bits.append(f"tokens `{total_tokens}` ({p_tok or 0} prompt / {c_tok or 0} compl)")
    if "cost_usd" in saved:
        bits.append(f"custo USD `{saved['cost_usd']}`")
    if bits:
        st.caption(" · ".join(bits))

telemetry_by_case = {
    (item["id"], item["version"]): item
    for item in saved.get("cases", [])
    if "id" in item and "version" in item
}

try:
    summary = score_path(experiment)
except (OSError, ValueError, KeyError) as exc:
    st.error(f"Não consegui pontuar este experimento: {exc}")
    st.stop()

versions = list(summary["metrics"])
metric_rows = [{"version": version, **values} for version, values in summary["metrics"].items()]
st.subheader("Acurácia")
st.dataframe(metric_rows, hide_index=True, width="stretch")

if versions:
    cols = st.columns(len(versions))
    for i, (v, row) in enumerate(summary["metrics"].items()):
        with cols[i]:
            rate = row.get("pass_rate", 0.0)
            delta_str = None
            if "field_accuracy" in row:
                delta_str = f"Campos: {row['field_accuracy'] * 100:.1f}%"
            st.metric(
                label=f"Taxa de sucesso ({v})",
                value=f"{rate * 100:.1f}%",
                delta=delta_str,
                help=f"JSON ok: {row.get('json_ok', 0)}/{row.get('cases', 0)} | Linhas: {row.get('rows_match', 0)}/{row.get('cases', 0)}",
            )

cases = sorted({item["id"] for item in summary["cases"]})
case_id = st.selectbox("Caso", cases)
version = st.radio("Versão do prompt", versions, horizontal=True)

match = next(
    (item for item in summary["cases"] if item["id"] == case_id and item["version"] == version),
    None,
)
if match is None:
    if summary.get("cases"):
        match = summary["cases"][0]
        case_id = match["id"]
        version = match["version"]
    else:
        st.warning("Nenhum caso encontrado.")
        st.stop()

telemetry = telemetry_by_case.get((case_id, version), {})

left, right = st.columns(2)
with left:
    st.subheader("Prompt")
    if match["rendered"]["system"]:
        st.markdown("**System**")
        st.code(match["rendered"]["system"], language="markdown")
    st.markdown("**Usuário**")
    st.code(match["rendered"]["prompt"], language="markdown")

    version_idx = versions.index(version) if version in versions else 0
    if len(versions) > 1 and version_idx > 0:
        prev_version = versions[version_idx - 1]
        prev_match = next(
            (item for item in summary["cases"] if item["id"] == case_id and item["version"] == prev_version),
            None,
        )
        if prev_match:
            def _format_prompt_lines(rendered: dict) -> list[str]:
                lines = []
                if rendered.get("system"):
                    lines.append("[SYSTEM]\n")
                    lines.extend(f"{l}\n" for l in rendered["system"].splitlines())
                    lines.append("\n")
                lines.append("[USER]\n")
                lines.extend(f"{l}\n" for l in rendered.get("prompt", "").splitlines())
                return lines

            prev_lines = _format_prompt_lines(prev_match["rendered"])
            curr_lines = _format_prompt_lines(match["rendered"])
            diff = list(
                difflib.unified_diff(
                    prev_lines,
                    curr_lines,
                    fromfile=f"versão {prev_version}",
                    tofile=f"versão {version}",
                )
            )
            diff_text = "".join(diff).strip() or "(nenhuma diferença no prompt)"
            with st.expander("Diff do prompt vs versão anterior", expanded=False):
                st.code(diff_text, language="diff")

with right:
    st.subheader("Saída registrada")
    st.code(match["output"] or "(ausente)", language="json" if match["json_ok"] else "text")
    passed = match["json_ok"] and match["rows_match"]
    status = "passou" if passed else "falhou"
    details = [
        f"JSON válido: `{match['json_ok']}`",
        f"Linhas corretas: `{match['rows_match']}`",
    ]
    if "sql_extracted" in match:
        details.insert(1, f"SQL extraído: `{match['sql_extracted']}`")
    if match.get("field_accuracy") is not None:
        details.append(f"Campos: `{match['field_accuracy']}`")

    latency = telemetry.get("latency_s", match.get("latency_s"))
    p_tokens = telemetry.get("prompt_tokens", match.get("prompt_tokens"))
    c_tokens = telemetry.get("completion_tokens", match.get("completion_tokens"))
    if latency is not None:
        details.append(f"Latência: `{latency}s`")
    if p_tokens is not None or c_tokens is not None:
        details.append(f"Tokens: `{p_tokens or 0} prompt / {c_tokens or 0} compl`")

    st.markdown(f"**{status}.** " + " ".join(details) + ".")
    if match["error"]:
        st.warning(match["error"])

    expected_rows = match.get("expected_rows")
    if expected_rows is None:
        try:
            inputs_data = load_yaml_mapping(experiment / "inputs.yaml")
            for c in inputs_data.get("cases", []):
                if c.get("id") == case_id:
                    expected_rows = c.get("expected_rows")
                    break
        except Exception:
            expected_rows = None

    actual_rows = match.get("actual_rows")

    st.markdown("##### Resultado Esperado vs Obtido")
    col_exp, col_act = st.columns(2)
    with col_exp:
        st.caption("Esperado")
        st.dataframe(expected_rows if expected_rows is not None else [], hide_index=True, width="stretch")
    with col_act:
        st.caption("Obtido")
        st.dataframe(actual_rows if actual_rows is not None else [], hide_index=True, width="stretch")
