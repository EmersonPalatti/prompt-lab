"""Pontua saídas registradas de um experimento de SQL.

As saídas ficam em `outputs/<versão>/<caso>.txt`. Este módulo não chama
provedor nenhum.
"""

from __future__ import annotations

import json
import re
from decimal import Decimal
from pathlib import Path

import duckdb
import yaml
from pydantic import ValidationError

from prompt_lab.schema import ExperimentSpec, SqlAnswer, is_single_statement

STATEMENT_TIMEOUT_MS = 5000
_FENCE = re.compile(r"```(?:sql|json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
_SELECT = re.compile(r"^(SELECT|WITH)\b", re.IGNORECASE)
_CREATE = re.compile(r"^CREATE\b", re.IGNORECASE)


def load_yaml_mapping(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} deve ser um mapeamento YAML")
    return data


def experiment_kind(experiment: Path) -> str:
    return str(load_yaml_mapping(experiment / "inputs.yaml").get("kind", "sql"))


def load_spec(path: Path) -> ExperimentSpec:
    return ExperimentSpec.model_validate(load_yaml_mapping(path))


def schema_text(setup: list[str]) -> str:
    creates = [item.strip() for item in setup if _CREATE.match(item.lstrip())]
    return "\n\n".join(creates)


def render_prompt(template: str, *, question: str, schema: str = "", rows: str = "") -> str:
    return (
        template.replace("{{question}}", question)
        .replace("{{schema}}", schema)
        .replace("{{rows}}", rows)
    )


def parse_sql(text: str) -> tuple[str | None, str | None]:
    """Devolve (sql, erro). Só aceita o JSON do modelo SqlAnswer."""

    try:
        answer = SqlAnswer.model_validate_json(text.strip())
    except ValidationError as exc:
        return None, exc.errors()[0]["msg"]
    return answer.sql, None


def extract_sql_for_diagnosis(text: str) -> str | None:
    """SQL fora do contrato. Não conta como json_ok."""

    stripped = text.strip()
    for fence in _FENCE.finditer(stripped):
        inner = fence.group(1).strip()
        sql, _ = parse_sql(inner)
        if sql:
            return sql
        if _SELECT.match(inner):
            return inner
    brace = re.search(r"\{[\s\S]*\}", stripped)
    if brace:
        sql, _ = parse_sql(brace.group(0))
        if sql:
            return sql
    if _SELECT.match(stripped):
        return stripped
    return None


def _normalize(value: object) -> object:
    if isinstance(value, Decimal):
        if value == value.to_integral_value():
            return int(value)
        return float(value)
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def _row_sort_key(row: tuple[tuple[str, object], ...]) -> list[tuple]:
    keyed = []
    for key, value in row:
        if value is None:
            keyed.append((key, 0, ""))
        elif isinstance(value, (int, float)):
            keyed.append((key, 1, value))
        else:
            keyed.append((key, 2, str(value)))
    return keyed


def row_set(rows: list[dict]) -> list[tuple[tuple[str, object], ...]]:
    normalized = [
        tuple(sorted((str(key), _normalize(value)) for key, value in row.items()))
        for row in rows
    ]
    return sorted(normalized, key=_row_sort_key)


def run_sql(setup: list[str], sql: str, timeout_ms: int = STATEMENT_TIMEOUT_MS) -> list[dict]:
    """Executa `sql` num DuckDB em memória, sem acesso a arquivos locais."""

    connection = duckdb.connect()
    try:
        connection.execute("SET enable_external_access = false")
        connection.execute(f"SET max_execution_time = {timeout_ms}")
        for statement in setup:
            connection.execute(statement)
        cursor = connection.execute(sql)
        if cursor.description is None:
            return []
        columns = [item[0] for item in cursor.description]
        return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
    finally:
        connection.close()


def list_versions(experiment: Path) -> list[str]:
    names = [
        path.name
        for path in experiment.iterdir()
        if path.is_dir() and (path / "prompt.md").is_file()
    ]
    return sorted(names)


def render_case(
    experiment: Path,
    version: str,
    question: str,
    schema: str = "",
    rows: str = "",
) -> dict:
    prompt_dir = experiment / version
    system_path = prompt_dir / "system.md"
    return {
        "system": render_prompt(
            system_path.read_text(encoding="utf-8"),
            question=question,
            schema=schema,
            rows=rows,
        )
        if system_path.is_file()
        else None,
        "prompt": render_prompt(
            (prompt_dir / "prompt.md").read_text(encoding="utf-8"),
            question=question,
            schema=schema,
            rows=rows,
        ),
    }


def prompts_for_run(experiment: Path) -> list[tuple[str, str, dict]]:
    """Lista (case_id, version, rendered) para o runner."""

    versions = list_versions(experiment)
    items: list[tuple[str, str, dict]] = []
    if experiment_kind(experiment) == "cleaning":
        from prompt_lab.cleaning import load_cleaning_spec

        spec = load_cleaning_spec(experiment / "inputs.yaml")
        for case in spec.cases:
            rows = json.dumps(case.input_rows, ensure_ascii=False, indent=2)
            for version in versions:
                items.append(
                    (
                        case.id,
                        version,
                        render_case(experiment, version, case.question, rows=rows),
                    )
                )
        return items

    spec = load_spec(experiment / "inputs.yaml")
    schema = schema_text(spec.setup)
    for case in spec.cases:
        for version in versions:
            items.append(
                (
                    case.id,
                    version,
                    render_case(experiment, version, case.question, schema),
                )
            )
    return items


def score_path(experiment: Path) -> dict:
    if experiment_kind(experiment) == "cleaning":
        from prompt_lab.cleaning import score_cleaning_experiment

        return score_cleaning_experiment(experiment)
    return score_experiment(experiment)


def _score_output(output: str, setup: list[str], expected_rows: list[dict]) -> dict:
    record = {
        "json_ok": False,
        "sql_extracted": False,
        "rows_match": False,
        "error": None,
        "output": output,
    }
    sql, parse_error = parse_sql(output)
    json_ok = sql is not None
    if sql is None:
        sql = extract_sql_for_diagnosis(output)
    if sql is None:
        record["error"] = parse_error or "SQL não extraído"
        return record

    record["json_ok"] = json_ok
    record["sql_extracted"] = True
    if not is_single_statement(sql):
        record["error"] = "sql deve ser um único statement"
        return record

    try:
        actual = run_sql(setup, sql)
    except duckdb.Error as exc:
        record["error"] = str(exc).splitlines()[0]
        return record

    record["rows_match"] = row_set(actual) == row_set(expected_rows)
    if not record["rows_match"]:
        record["error"] = "linhas diferentes do esperado"
    elif not json_ok:
        record["error"] = "JSON inválido (execução ok, diagnóstico)"
    return record


def score_experiment(experiment: Path) -> dict:
    spec = load_spec(experiment / "inputs.yaml")
    setup = spec.setup
    schema = schema_text(setup)
    versions = list_versions(experiment)
    scored_cases: list[dict] = []

    for case in spec.cases:
        for version in versions:
            output_path = experiment / "outputs" / version / f"{case.id}.txt"
            record = {
                "id": case.id,
                "version": version,
                "question": case.question,
                "rendered": render_case(experiment, version, case.question, schema),
                "json_ok": False,
                "sql_extracted": False,
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
                setup,
                case.expected_rows,
            )
            record.update(scored)
            scored_cases.append(record)

    metrics = {}
    for version in versions:
        version_cases = [item for item in scored_cases if item["version"] == version]
        total = len(version_cases)
        passed = sum(1 for item in version_cases if item["json_ok"] and item["rows_match"])
        metrics[version] = {
            "cases": total,
            "json_ok": sum(1 for item in version_cases if item["json_ok"]),
            "sql_extracted": sum(1 for item in version_cases if item["sql_extracted"]),
            "rows_match": sum(1 for item in version_cases if item["rows_match"]),
            "pass_rate": round(passed / total, 4) if total else 0.0,
        }

    return {
        "experiment": experiment.name,
        "note": (
            "Pontuação de outputs/ no DuckDB. Este passo não chama modelo."
        ),
        "metrics": metrics,
        "cases": scored_cases,
    }


_RUN_META = (
    "source",
    "model",
    "started_at",
    "finished_at",
    "cost_usd",
    "repeats",
    "prompt_tokens",
    "completion_tokens",
    "note",
)


def public_payload(summary: dict) -> dict:
    public_cases = []
    for item in summary["cases"]:
        row = {
            "id": item["id"],
            "version": item["version"],
            "json_ok": item["json_ok"],
            "rows_match": item["rows_match"],
            "error": item["error"],
        }
        for key in ("sql_extracted", "field_accuracy", "latency_s", "prompt_tokens", "completion_tokens"):
            if item.get(key) is not None:
                row[key] = item[key]
        public_cases.append(row)

    return {
        "experiment": summary["experiment"],
        "note": summary["note"],
        "metrics": summary["metrics"],
        "cases": public_cases,
    }


def write_results(experiment: Path, summary: dict | None = None, extra: dict | None = None) -> Path:
    summary = summary or score_path(experiment)
    destination = experiment / "results.json"
    existing: dict = {}
    if destination.is_file():
        existing = json.loads(destination.read_text(encoding="utf-8"))

    payload = public_payload(summary)
    extra = extra or {}
    for key in _RUN_META:
        if key in extra:
            payload[key] = extra[key]
        elif key in existing:
            payload[key] = existing[key]
    payload.setdefault("source", summary.get("source", "outputs"))

    previous = {(item.get("id"), item.get("version")): item for item in existing.get("cases", [])}
    for row in payload["cases"]:
        prev = previous.get((row["id"], row["version"]), {})
        for key in ("latency_s", "prompt_tokens", "completion_tokens"):
            if key not in row and key in prev:
                row[key] = prev[key]

    payload["prompt_tokens"] = sum(int(item.get("prompt_tokens") or 0) for item in payload["cases"])
    payload["completion_tokens"] = sum(int(item.get("completion_tokens") or 0) for item in payload["cases"])
    if "started_at" in existing:
        payload["started_at"] = existing["started_at"]

    destination.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return destination
