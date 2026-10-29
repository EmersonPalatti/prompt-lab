"""Utilitários comuns compartilhados entre experiment, cleaning e runner."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import yaml


def load_yaml_mapping(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} deve ser um mapeamento YAML")
    return data


def experiment_kind(experiment: Path) -> str:
    return str(load_yaml_mapping(experiment / "inputs.yaml").get("kind", "sql"))


def render_prompt(
    template: str, *, question: str, schema: str = "", rows: str = ""
) -> str:
    return (
        template.replace("{{question}}", question)
        .replace("{{schema}}", schema)
        .replace("{{rows}}", rows)
    )


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


def _normalize(value: object) -> object:
    if isinstance(value, Decimal):
        if value == value.to_integral_value():
            return int(value)
        return round(float(value), 6)
    if isinstance(value, float):
        if value.is_integer():
            return int(value)
        return round(value, 6)
    return value
