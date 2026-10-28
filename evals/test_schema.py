import pytest
from pydantic import ValidationError

from prompt_lab.schema import ExperimentSpec, SqlAnswer


def test_sql_answer_rejects_empty_query():
    with pytest.raises(ValidationError):
        SqlAnswer.model_validate_json('{"sql": ""}')


def test_sql_answer_rejects_extra_keys():
    with pytest.raises(ValidationError):
        SqlAnswer.model_validate_json('{"sql": "SELECT 1", "note": "x"}')


def test_sql_answer_rejects_multiple_statements():
    with pytest.raises(ValidationError):
        SqlAnswer.model_validate_json('{"sql": "SELECT 1; SELECT 2"}')


def test_sql_answer_allows_trailing_semicolon():
    answer = SqlAnswer.model_validate_json('{"sql": "SELECT 1 AS n;"}')
    assert answer.sql == "SELECT 1 AS n;"


def test_experiment_spec_requires_cases():
    with pytest.raises(ValidationError):
        ExperimentSpec.model_validate({"setup": ["CREATE TABLE t (n INTEGER)"]})
