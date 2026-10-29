"""Prompt Lab: pipeline de avaliação para LLM em tarefas de dados."""

from prompt_lab.experiment import score_path, write_results
from prompt_lab.schema import (
    CleanAnswer,
    CleaningSpec,
    ExperimentSpec,
    SqlAnswer,
    SqlOrErrorAnswer,
)

__version__ = "0.1.0"

__all__ = [
    "CleanAnswer",
    "CleaningSpec",
    "ExperimentSpec",
    "SqlAnswer",
    "SqlOrErrorAnswer",
    "__version__",
    "score_path",
    "write_results",
]
