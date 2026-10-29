"""Pontua saídas de limpeza de dados. Não chama provedor."""

from __future__ import annotations

import json
import re
from pathlib import Path

from pydantic import ValidationError

from prompt_lab.common import (
    _normalize,
    experiment_kind,
    list_versions,
    load_yaml_mapping,
    render_case,
)
from prompt_lab.schema import CleanAnswer, CleaningSpec

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
_COMPARE_KEYS = ("city", "status", "amount")


def load_cleaning_spec(path: Path) -> CleaningSpec:
    return CleaningSpec.model_validate(load_yaml_mapping(path))


def parse_clean(text: str) -> tuple[list[dict] | None, str | None]:
    try:
        answer = CleanAnswer.model_validate_json(text.strip())
    except ValidationError as exc:
        return None, exc.errors()[0]["msg"]
    return [row.model_dump() for row in answer.rows], None


def extract_clean_for_diagnosis(text: str) -> list[dict] | None:
    stripped = text.strip()
    for fence in _FENCE.finditer(stripped):
        rows, _ = parse_clean(fence.group(1).strip())
        if rows is not None:
            return rows
    brace = re.search(r"\{[\s\S]*\}", stripped)
    if brace:
        rows, _ = parse_clean(brace.group(0))
        if rows is not None:
            return rows
    return None


def field_score(
    actual: list[dict],
    expected: list[dict],
    compare_keys: tuple[str, ...] = _COMPARE_KEYS,
) -> tuple[float, bool]:
    expected_by_id = {row["id"]: row for row in expected}
    actual_by_id = {row["id"]: row for row in actual}
    has_duplicates = len(actual_by_id) != len(actual)
    extra = set(actual_by_id) - set(expected_by_id)
    denom_rows = max(len(expected), len(actual)) if (has_duplicates or extra) else len(expected)
    total = denom_rows * len(compare_keys)
    hits = 0
    for row_id, expected_row in expected_by_id.items():
        actual_row = actual_by_id.get(row_id)
        if actual_row is None:
            continue
        for key in compare_keys:
            if _normalize(actual_row.get(key)) == _normalize(expected_row.get(key)):
                hits += 1

    rows_match = (
        not has_duplicates
        and len(actual) == len(expected)
        and not extra
        and hits == (len(expected) * len(compare_keys))
        and set(actual_by_id) == set(expected_by_id)
    )
    accuracy = round(hits / total, 4) if total else 0.0
    return accuracy, rows_match


def _score_output(
    output: str,
    expected_rows: list[dict],
    compare_keys: tuple[str, ...] = _COMPARE_KEYS,
) -> dict:
    record = {
        "json_ok": False,
        "field_accuracy": 0.0,
        "rows_match": False,
        "actual_rows": None,
        "error": None,
        "output": output,
    }
    rows, parse_error = parse_clean(output)
    json_ok = rows is not None
    if rows is None:
        rows = extract_clean_for_diagnosis(output)
    if rows is None:
        record["error"] = parse_error or "JSON de rows não extraído"
        return record

    record["json_ok"] = json_ok
    record["actual_rows"] = rows
    accuracy, rows_match = field_score(rows, expected_rows, compare_keys=compare_keys)
    record["field_accuracy"] = accuracy
    record["rows_match"] = rows_match
    if not rows_match:
        record["error"] = "campos diferentes do esperado"
    elif not json_ok:
        record["error"] = "JSON inválido (campos ok, diagnóstico)"
    return record


def score_cleaning_experiment(experiment: Path) -> dict:
    if experiment_kind(experiment) != "cleaning":
        raise ValueError(f"{experiment} não é kind: cleaning")

    spec = load_cleaning_spec(experiment / "inputs.yaml")
    compare_keys = spec.compare_keys
    versions = list_versions(experiment)
    scored_cases: list[dict] = []

    for case in spec.cases:
        rows_text = json.dumps(case.input_rows, ensure_ascii=False, indent=2)
        for version in versions:
            output_path = experiment / "outputs" / version / f"{case.id}.txt"
            record = {
                "id": case.id,
                "version": version,
                "question": case.question,
                "expected_rows": case.expected_rows,
                "actual_rows": None,
                "rendered": render_case(
                    experiment, version, case.question, rows=rows_text
                ),
                "json_ok": False,
                "field_accuracy": 0.0,
                "rows_match": False,
                "error": None,
                "output": None,
            }
            if not output_path.is_file():
                record["error"] = "saída registrada ausente"
                scored_cases.append(record)
                continue
            scored = _score_output(
                output_path.read_text(encoding="utf-8").strip(),
                case.expected_rows,
                compare_keys=compare_keys,
            )
            record.update(scored)
            scored_cases.append(record)

    metrics = {}
    for version in versions:
        version_cases = [item for item in scored_cases if item["version"] == version]
        total = len(version_cases)
        passed = sum(1 for item in version_cases if item["json_ok"] and item["rows_match"])
        field_mean = (
            sum(item["field_accuracy"] for item in version_cases) / total if total else 0.0
        )
        metrics[version] = {
            "cases": total,
            "json_ok": sum(1 for item in version_cases if item["json_ok"]),
            "rows_match": sum(1 for item in version_cases if item["rows_match"]),
            "field_accuracy": round(field_mean, 4),
            "pass_rate": round(passed / total, 4) if total else 0.0,
        }

    return {
        "experiment": experiment.name,
        "note": "Pontuação de outputs/ por campos. Este passo não chama modelo.",
        "metrics": metrics,
        "cases": scored_cases,
    }
