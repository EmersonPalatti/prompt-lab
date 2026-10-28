from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SqlAnswer(BaseModel):
    """Contrato da v2: um objeto JSON só com a consulta em `sql`."""

    model_config = ConfigDict(extra="forbid")

    sql: str = Field(min_length=1)

    @field_validator("sql")
    @classmethod
    def single_statement(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("sql não pode ser vazio")
        if not is_single_statement(stripped):
            raise ValueError("sql deve ser um único statement")
        return stripped


class CaseSpec(BaseModel):
    id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    expected_rows: list[dict[str, Any]]


class ExperimentSpec(BaseModel):
    kind: Literal["sql"] = "sql"
    setup: list[str] = Field(min_length=1)
    cases: list[CaseSpec] = Field(min_length=1)


class CleanRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    city: str | None
    status: str = Field(min_length=1)
    amount: int


class CleanAnswer(BaseModel):
    """Contrato da v2 de limpeza: um objeto JSON só com `rows`."""

    model_config = ConfigDict(extra="forbid")

    rows: list[CleanRow]


class CleaningCaseSpec(BaseModel):
    id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    input_rows: list[dict[str, Any]]
    expected_rows: list[dict[str, Any]]


class CleaningSpec(BaseModel):
    kind: Literal["cleaning"]
    cases: list[CleaningCaseSpec] = Field(min_length=1)


def is_single_statement(sql: str) -> bool:
    body = sql.strip()
    if body.endswith(";"):
        body = body[:-1]
    return ";" not in body
