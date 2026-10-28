"""Chama um modelo via LiteLLM e grava outputs/ de um experimento."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path

from prompt_lab.experiment import (
    list_versions,
    load_spec,
    render_case,
    schema_text,
    score_experiment,
    write_results,
)

DEFAULT_MODEL = "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free"
MAX_TOKENS = 1024
TEMPERATURE = 0
REQUEST_TIMEOUT_S = 120
MAX_RETRIES = 3
ROOT = Path(__file__).resolve().parents[2]


@dataclass
class ModelReply:
    content: str
    prompt_tokens: int
    completion_tokens: int
    latency_s: float
    cost_usd: float


class RateLimitError(RuntimeError):
    """429 persistente; parar o run para não queimar a cota."""


def _load_env() -> None:
    import truststore
    from dotenv import load_dotenv

    truststore.inject_into_ssl()
    load_dotenv(ROOT / ".env")
    os.environ.setdefault("LITELLM_LOG", "ERROR")


def call_model(messages: list[dict], model: str) -> ModelReply:
    from litellm import completion
    from litellm.exceptions import RateLimitError as LiteRateLimitError

    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES):
        started = time.perf_counter()
        try:
            response = completion(
                model=model,
                messages=messages,
                temperature=TEMPERATURE,
                max_tokens=MAX_TOKENS,
                timeout=REQUEST_TIMEOUT_S,
                extra_headers={"X-Title": "Prompt Lab"},
            )
        except LiteRateLimitError as exc:
            last_error = exc
            retry_after = getattr(exc, "retry_after", None) or 2 ** attempt
            if attempt == MAX_RETRIES - 1:
                raise RateLimitError("rate limit persistente no OpenRouter") from exc
            time.sleep(float(retry_after))
            continue

        latency_s = time.perf_counter() - started
        content = response.choices[0].message.content or ""
        usage = getattr(response, "usage", None)
        hidden = getattr(response, "_hidden_params", None) or {}
        return ModelReply(
            content=content,
            prompt_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
            completion_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
            latency_s=round(latency_s, 3),
            cost_usd=float(hidden.get("response_cost") or 0.0),
        )

    raise RateLimitError("rate limit persistente no OpenRouter") from last_error


def run_experiment(
    experiment: Path,
    *,
    model: str = DEFAULT_MODEL,
    repeats: int = 1,
    versions: list[str] | None = None,
    call=call_model,
) -> Path:
    if repeats != 1:
        raise ValueError("repeats diferente de 1 ainda não é suportado")

    _load_env()
    if not os.environ.get("OPENROUTER_API_KEY"):
        raise RuntimeError("OPENROUTER_API_KEY ausente. Copie .env.example para .env.")

    spec = load_spec(experiment / "inputs.yaml")
    schema = schema_text(spec.setup)
    available = list_versions(experiment)
    selected = versions or available
    missing = [name for name in selected if name not in available]
    if missing:
        raise ValueError(f"versão inexistente: {', '.join(missing)}")
    versions = selected
    started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    usages: dict[tuple[str, str], dict] = {}
    prompt_tokens = 0
    completion_tokens = 0
    cost_usd = 0.0
    fatal: Exception | None = None

    try:
        for case in spec.cases:
            for version in versions:
                rendered = render_case(experiment, version, case.question, schema)
                messages = []
                if rendered["system"]:
                    messages.append({"role": "system", "content": rendered["system"]})
                messages.append({"role": "user", "content": rendered["prompt"]})
                print(f"{version}/{case.id}", flush=True)
                reply = call(messages, model)
                output_dir = experiment / "outputs" / version
                output_dir.mkdir(parents=True, exist_ok=True)
                (output_dir / f"{case.id}.txt").write_text(reply.content, encoding="utf-8")
                usages[(version, case.id)] = {
                    "latency_s": reply.latency_s,
                    "prompt_tokens": reply.prompt_tokens,
                    "completion_tokens": reply.completion_tokens,
                }
                prompt_tokens += reply.prompt_tokens
                completion_tokens += reply.completion_tokens
                cost_usd += reply.cost_usd
    except Exception as exc:
        fatal = exc

    summary = score_experiment(experiment)
    for item in summary["cases"]:
        extra = usages.get((item["version"], item["id"]))
        if extra:
            item.update(extra)

    destination = write_results(
        experiment,
        summary,
        extra={
            "source": "openrouter",
            "model": model,
            "started_at": started_at,
            "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "cost_usd": round(cost_usd, 6),
            "repeats": repeats,
            "note": (
                "Saídas gravadas por LiteLLM/OpenRouter em outputs/. "
                "A pontuação é local, no DuckDB."
            ),
        },
    )
    if fatal:
        raise fatal
    return destination
