import pytest
from pydantic import ValidationError

from prompt_lab.schema import CleanAnswer, ExperimentSpec, SqlAnswer, SqlOrErrorAnswer


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


def test_sql_answer_allows_semicolon_in_string_literal():
    answer = SqlAnswer.model_validate_json('{"sql": "SELECT \'a;b\' AS s;"}')
    assert answer.sql == "SELECT 'a;b' AS s;"


def test_sql_answer_allows_semicolon_in_escaped_quote_literal():
    answer = SqlAnswer.model_validate_json('{"sql": "SELECT \'a\'\'b;c\' AS s"}')
    assert answer.sql == "SELECT 'a''b;c' AS s"


def test_sql_answer_rejects_multiple_statements_with_semicolon_in_literal():
    with pytest.raises(ValidationError):
        SqlAnswer.model_validate_json('{"sql": "SELECT \'a;b\'; SELECT 2"}')


def test_experiment_spec_requires_cases():
    with pytest.raises(ValidationError):
        ExperimentSpec.model_validate({"setup": ["CREATE TABLE t (n INTEGER)"]})


def test_clean_answer_requires_rows():
    with pytest.raises(ValidationError):
        CleanAnswer.model_validate_json("{}")


def test_sql_or_error_accepts_sql():
    answer = SqlOrErrorAnswer.model_validate_json('{"sql": "SELECT 1 AS n"}')
    assert answer.sql == "SELECT 1 AS n"
    assert answer.error is None


def test_sql_or_error_accepts_error():
    answer = SqlOrErrorAnswer.model_validate_json('{"error": "coluna inexistente"}')
    assert answer.sql is None
    assert answer.error == "coluna inexistente"


def test_sql_or_error_rejects_both():
    with pytest.raises(ValidationError):
        SqlOrErrorAnswer.model_validate_json('{"sql": "SELECT 1", "error": "falha"}')


def test_sql_or_error_rejects_empty():
    with pytest.raises(ValidationError):
        SqlOrErrorAnswer.model_validate_json("{}")
    with pytest.raises(ValidationError):
        SqlOrErrorAnswer.model_validate_json('{"sql": ""}')
    with pytest.raises(ValidationError):
        SqlOrErrorAnswer.model_validate_json('{"error": ""}')
    with pytest.raises(ValidationError):
        SqlOrErrorAnswer.model_validate_json('{"sql": "   "}')
    with pytest.raises(ValidationError):
        SqlOrErrorAnswer.model_validate_json('{"error": "   "}')


def test_sql_or_error_rejects_extra_keys():
    with pytest.raises(ValidationError):
        SqlOrErrorAnswer.model_validate_json('{"sql": "SELECT 1", "extra": 1}')
    with pytest.raises(ValidationError):
        SqlOrErrorAnswer.model_validate_json('{"error": "motivo", "extra": 1}')


def test_sql_or_error_rejects_multiple_statements():
    with pytest.raises(ValidationError):
        SqlOrErrorAnswer.model_validate_json('{"sql": "SELECT 1; SELECT 2"}')
