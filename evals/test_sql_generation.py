import json
from pathlib import Path

import duckdb
import pytest

from prompt_lab.experiment import (
    extract_sql_for_diagnosis,
    load_spec,
    parse_sql,
    run_sql,
    score_experiment,
    write_results,
)

EXPERIMENT = Path(__file__).resolve().parents[1] / "experiments" / "001-sql-generation"


def _write_experiment(
    root: Path,
    *,
    inputs: str,
    prompt: str = "{{question}}\n{{schema}}\n",
    outputs: dict[str, str],
) -> Path:
    version = root / "v1"
    output_dir = root / "outputs" / "v1"
    version.mkdir(parents=True)
    output_dir.mkdir(parents=True)
    (version / "prompt.md").write_text(prompt, encoding="utf-8")
    (root / "inputs.yaml").write_text(inputs, encoding="utf-8")
    for case_id, text in outputs.items():
        (output_dir / f"{case_id}.txt").write_text(text, encoding="utf-8")
    return root


def test_parse_sql_accepts_contract():
    sql, error = parse_sql('{"sql": "SELECT 1 AS n"}')
    assert error is None
    assert sql == "SELECT 1 AS n"


def test_extract_sql_from_markdown_fence():
    text = "A consulta:\n\n```sql\nSELECT city, SUM(amount) AS total FROM orders GROUP BY city\n```\n"
    assert extract_sql_for_diagnosis(text).startswith("SELECT city")


def test_bare_select_is_diagnosis_not_contract():
    text = "SELECT COUNT(*) AS n FROM orders WHERE status = 'open'"
    sql, error = parse_sql(text)
    assert sql is None
    assert error is not None
    assert extract_sql_for_diagnosis(text) == text


def test_json_ok_false_but_rows_can_match(tmp_path: Path):
    experiment = _write_experiment(
        tmp_path / "exp",
        inputs="\n".join(
            [
                "setup:",
                "  - CREATE TABLE t (n INTEGER)",
                "  - INSERT INTO t VALUES (1)",
                "cases:",
                "  - id: one",
                "    question: conte",
                "    expected_rows:",
                "      - n: 1",
                "",
            ]
        ),
        outputs={"one": "SELECT n FROM t"},
    )

    summary = score_experiment(experiment)
    case = summary["cases"][0]
    assert case["json_ok"] is False
    assert case["sql_extracted"] is True
    assert case["rows_match"] is True
    assert summary["metrics"]["v1"]["pass_rate"] == 0.0


def test_pass_rate_needs_json_and_rows(tmp_path: Path):
    experiment = _write_experiment(
        tmp_path / "exp",
        inputs="\n".join(
            [
                "setup:",
                "  - CREATE TABLE t (n INTEGER)",
                "  - INSERT INTO t VALUES (1)",
                "cases:",
                "  - id: one",
                "    question: conte",
                "    expected_rows:",
                "      - n: 1",
                "",
            ]
        ),
        outputs={"one": '{"sql": "SELECT n FROM t"}'},
    )

    summary = score_experiment(experiment)
    assert summary["metrics"]["v1"]["pass_rate"] == 1.0
    assert "field_accuracy" not in summary["metrics"]["v1"]


def test_null_values_can_be_compared(tmp_path: Path):
    experiment = _write_experiment(
        tmp_path / "exp",
        inputs="\n".join(
            [
                "setup:",
                "  - CREATE TABLE t (city VARCHAR, n INTEGER)",
                "  - INSERT INTO t VALUES (NULL, 1), ('Recife', 2)",
                "cases:",
                "  - id: cities",
                "    question: liste",
                "    expected_rows:",
                "      - city: Recife",
                "        n: 2",
                "      - city:",
                "        n: 1",
                "",
            ]
        ),
        outputs={"cities": '{"sql": "SELECT city, n FROM t"}'},
    )

    summary = score_experiment(experiment)
    assert summary["cases"][0]["rows_match"] is True


def test_row_order_does_not_matter(tmp_path: Path):
    experiment = _write_experiment(
        tmp_path / "exp",
        inputs="\n".join(
            [
                "setup:",
                "  - CREATE TABLE t (city VARCHAR, total INTEGER)",
                "  - INSERT INTO t VALUES ('Recife', 5), ('Sao Paulo', 30)",
                "cases:",
                "  - id: cities",
                "    question: liste",
                "    expected_rows:",
                "      - city: Sao Paulo",
                "        total: 30",
                "      - city: Recife",
                "        total: 5",
                "",
            ]
        ),
        outputs={"cities": '{"sql": "SELECT city, total FROM t ORDER BY city DESC"}'},
    )

    summary = score_experiment(experiment)
    assert summary["cases"][0]["rows_match"] is True


def test_sql_cannot_read_local_files(tmp_path: Path):
    secret = tmp_path / "secret.csv"
    secret.write_text("city,total\nX,1\n", encoding="utf-8")
    escaped = secret.as_posix().replace("'", "''")
    with pytest.raises(duckdb.Error):
        run_sql(
            ["CREATE TABLE t (city VARCHAR, total INTEGER)"],
            f"SELECT * FROM read_csv_auto('{escaped}')",
        )


def test_sql_times_out_on_heavy_query():
    with pytest.raises(duckdb.Error, match="maximum execution time"):
        run_sql(
            ["CREATE TABLE t (n INTEGER)"],
            "SELECT sum(i) FROM range(1000000000) t(i)",
            timeout_ms=200,
        )


def test_write_results_does_not_touch_repo_experiment(tmp_path: Path):
    experiment = _write_experiment(
        tmp_path / "exp",
        inputs="\n".join(
            [
                "setup:",
                "  - CREATE TABLE t (n INTEGER)",
                "  - INSERT INTO t VALUES (1)",
                "cases:",
                "  - id: one",
                "    question: conte",
                "    expected_rows:",
                "      - n: 1",
                "",
            ]
        ),
        outputs={"one": '{"sql": "SELECT n FROM t"}'},
    )
    repo_results = EXPERIMENT / "results.json"
    before = repo_results.read_text(encoding="utf-8") if repo_results.is_file() else None

    destination = write_results(experiment)
    saved = json.loads(destination.read_text(encoding="utf-8"))
    fresh = score_experiment(experiment)

    assert saved["metrics"] == fresh["metrics"]
    assert destination != repo_results
    after = repo_results.read_text(encoding="utf-8") if repo_results.is_file() else None
    assert after == before


def test_001_spec_has_six_cases():
    spec = load_spec(EXPERIMENT / "inputs.yaml")
    assert [case.id for case in spec.cases] == [
        "paid_by_city",
        "open_count",
        "gmv_by_restaurant",
        "unknown_column",
        "null_city",
        "top_city",
    ]
    summary = score_experiment(EXPERIMENT)
    assert {"v1", "v2", "v3"} <= set(summary["metrics"])
    assert summary["metrics"]["v1"]["cases"] == 6
    assert summary["metrics"]["v2"]["cases"] == 6
    assert summary["metrics"]["v3"]["cases"] == 6


def test_committed_results_match_scorer_when_present():
    path = EXPERIMENT / "results.json"
    if not path.is_file():
        pytest.skip("results.json ainda não foi gerado")
    saved = json.loads(path.read_text(encoding="utf-8"))
    fresh = score_experiment(EXPERIMENT)
    saved_v1 = saved.get("metrics", {}).get("v1", {})
    if "pass_rate" not in saved_v1 or saved_v1.get("cases") != fresh["metrics"]["v1"]["cases"]:
        pytest.skip("results.json desatualizado")
    for version, saved_metrics in saved["metrics"].items():
        assert saved_metrics == fresh["metrics"][version]
    saved_rows = [
        (item["id"], item["version"], item["json_ok"], item["rows_match"])
        for item in saved["cases"]
    ]
    fresh_rows = [
        (item["id"], item["version"], item["json_ok"], item["rows_match"])
        for item in fresh["cases"]
        if (item["id"], item["version"]) in {(row[0], row[1]) for row in saved_rows}
    ]
    assert saved_rows == fresh_rows
