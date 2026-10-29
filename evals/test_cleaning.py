import json
from pathlib import Path

from pydantic import ValidationError
import pytest

from prompt_lab.cleaning import field_score, parse_clean, score_cleaning_experiment
from prompt_lab.experiment import experiment_kind, score_path
from prompt_lab.schema import CleanAnswer

EXPERIMENT = Path(__file__).resolve().parents[1] / "experiments" / "002-data-cleaning"


def _write_cleaning(root: Path, *, output: str) -> Path:
    version = root / "v1"
    output_dir = root / "outputs" / "v1"
    version.mkdir(parents=True)
    output_dir.mkdir(parents=True)
    (version / "prompt.md").write_text("{{rows}}\n{{question}}\n", encoding="utf-8")
    (root / "inputs.yaml").write_text(
        "\n".join(
            [
                "kind: cleaning",
                "cases:",
                "  - id: one",
                "    question: limpe",
                "    input_rows:",
                "      - id: 1",
                "        city: S. Paulo",
                "        status: PAID",
                "        amount: 10",
                "    expected_rows:",
                "      - id: 1",
                "        city: Sao Paulo",
                "        status: paid",
                "        amount: 10",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (output_dir / "one.txt").write_text(output, encoding="utf-8")
    return root


def test_clean_answer_rejects_extra_keys():
    with pytest.raises(ValidationError):
        CleanAnswer.model_validate_json(
            '{"rows": [{"id": 1, "city": "Sao Paulo", "status": "paid", "amount": 10, "notes": "vip"}]}'
        )


def test_parse_clean_accepts_contract():
    rows, error = parse_clean(
        '{"rows": [{"id": 1, "city": null, "status": "open", "amount": 3}]}'
    )
    assert error is None
    assert rows == [{"id": 1, "city": None, "status": "open", "amount": 3}]


def test_field_score_partial():
    actual = [{"id": 1, "city": "Recife", "status": "paid", "amount": 10}]
    expected = [{"id": 1, "city": "Sao Paulo", "status": "paid", "amount": 10}]
    accuracy, rows_match = field_score(actual, expected)
    assert rows_match is False
    assert accuracy == round(2 / 3, 4)


def test_field_score_penalizes_extra_rows():
    actual = [
        {"id": 1, "city": "Sao Paulo", "status": "paid", "amount": 10},
        {"id": 2, "city": "Rio", "status": "paid", "amount": 20},
    ]
    expected = [
        {"id": 1, "city": "Sao Paulo", "status": "paid", "amount": 10},
    ]
    accuracy, rows_match = field_score(actual, expected)
    assert rows_match is False
    assert accuracy == round(3 / 6, 4)


def test_field_score_penalizes_duplicate_ids():
    actual = [
        {"id": 1, "city": "Sao Paulo", "status": "paid", "amount": 10},
        {"id": 1, "city": "Sao Paulo", "status": "paid", "amount": 10},
    ]
    expected = [
        {"id": 1, "city": "Sao Paulo", "status": "paid", "amount": 10},
    ]
    accuracy, rows_match = field_score(actual, expected)
    assert rows_match is False
    assert accuracy == round(3 / 6, 4)


def test_field_score_custom_compare_keys():
    actual = [{"id": 1, "status": "paid"}]
    expected = [{"id": 1, "status": "paid"}]
    accuracy, rows_match = field_score(actual, expected, compare_keys=("status",))
    assert rows_match is True
    assert accuracy == 1.0


def test_pass_rate_needs_json_and_rows(tmp_path: Path):
    experiment = _write_cleaning(
        tmp_path / "exp",
        output='{"rows": [{"id": 1, "city": "Sao Paulo", "status": "paid", "amount": 10}]}',
    )
    summary = score_cleaning_experiment(experiment)
    assert summary["metrics"]["v1"]["pass_rate"] == 1.0
    assert summary["metrics"]["v1"]["field_accuracy"] == 1.0
    assert summary["cases"][0]["json_ok"] is True
    assert summary["cases"][0]["expected_rows"] == [
        {"id": 1, "city": "Sao Paulo", "status": "paid", "amount": 10}
    ]
    assert summary["cases"][0]["actual_rows"] == [
        {"id": 1, "city": "Sao Paulo", "status": "paid", "amount": 10}
    ]


def test_text_output_does_not_pass(tmp_path: Path):
    experiment = _write_cleaning(tmp_path / "exp", output="Sao Paulo, paid, 10")
    summary = score_cleaning_experiment(experiment)
    case = summary["cases"][0]
    assert case["json_ok"] is False
    assert case["rows_match"] is False
    assert summary["metrics"]["v1"]["pass_rate"] == 0.0


def test_002_is_cleaning_with_six_cases():
    assert experiment_kind(EXPERIMENT) == "cleaning"
    summary = score_path(EXPERIMENT)
    assert summary["experiment"] == "002-data-cleaning"
    assert [item["id"] for item in summary["cases"] if item["version"] == "v1"] == [
        "city_typo",
        "status_synonym",
        "null_city",
        "mixed_batch",
        "unknown_status",
        "extra_notes",
    ]
    assert set(summary["metrics"]) == {"v1", "v2"}
    assert summary["metrics"]["v1"]["cases"] == 6


def test_002_committed_results_match_scorer():
    path = EXPERIMENT / "results.json"
    saved = json.loads(path.read_text(encoding="utf-8"))
    fresh = score_path(EXPERIMENT)
    assert saved["metrics"] == fresh["metrics"]
    assert saved["source"] == "openrouter"
