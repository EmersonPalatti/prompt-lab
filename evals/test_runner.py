from pathlib import Path
import sys
import time

import litellm
from litellm.exceptions import RateLimitError as LiteRateLimitError
import pytest

from prompt_lab.__main__ import main
from prompt_lab.runner import ModelReply, RateLimitError, call_model, run_experiment


def _write_experiment(root: Path) -> Path:
    version = root / "v1"
    version.mkdir(parents=True)
    (version / "prompt.md").write_text("{{question}}\n{{schema}}\n", encoding="utf-8")
    (root / "inputs.yaml").write_text(
        "\n".join(
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
        encoding="utf-8",
    )
    return root


def test_run_writes_outputs_and_results(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    experiment = _write_experiment(tmp_path / "exp")
    calls: list[tuple] = []

    def fake_call(messages, model):
        calls.append((messages, model))
        return ModelReply(
            content='{"sql": "SELECT n FROM t"}',
            prompt_tokens=4,
            completion_tokens=6,
            latency_s=0.01,
            cost_usd=0.0,
        )

    destination = run_experiment(experiment, call=fake_call, model="openrouter/test")
    output = (experiment / "outputs" / "v1" / "one.txt").read_text(encoding="utf-8")
    assert output == '{"sql": "SELECT n FROM t"}'
    assert calls and calls[0][1] == "openrouter/test"
    saved = destination.read_text(encoding="utf-8")
    assert '"source": "openrouter"' in saved
    assert '"pass_rate": 1.0' in saved
    assert '"prompt_tokens": 4' in saved


def test_run_can_target_one_version(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    experiment = _write_experiment(tmp_path / "exp")
    v2 = experiment / "v2"
    v2.mkdir()
    (v2 / "prompt.md").write_text("{{question}}\n{{schema}}\n", encoding="utf-8")
    called: list[str] = []

    def fake_call(messages, model):
        called.append(messages[-1]["content"])
        return ModelReply(
            content='{"sql": "SELECT n FROM t"}',
            prompt_tokens=1,
            completion_tokens=1,
            latency_s=0.01,
            cost_usd=0.0,
        )

    run_experiment(experiment, call=fake_call, versions=["v2"])
    assert (experiment / "outputs" / "v2" / "one.txt").is_file()
    assert not (experiment / "outputs" / "v1" / "one.txt").is_file()
    assert len(called) == 1


def test_call_model_retries_and_succeeds(monkeypatch):
    sleep_calls: list[float] = []
    monkeypatch.setattr(time, "sleep", lambda s: sleep_calls.append(s))

    class DummyMessage:
        content = '{"sql": "SELECT 1"}'

    class DummyChoice:
        message = DummyMessage()

    class DummyUsage:
        prompt_tokens = 5
        completion_tokens = 5

    class DummyResponse:
        choices = [DummyChoice()]
        usage = DummyUsage()
        _hidden_params = {"response_cost": 0.001}

    attempts = 0

    def mock_completion(**kwargs):
        nonlocal attempts
        attempts += 1
        if attempts < 2:
            raise LiteRateLimitError(
                "rate limited", llm_provider="openrouter", model="test"
            )
        return DummyResponse()

    monkeypatch.setattr(litellm, "completion", mock_completion)

    reply = call_model([{"role": "user", "content": "hi"}], "test-model")
    assert attempts == 2
    assert len(sleep_calls) == 1
    assert reply.content == '{"sql": "SELECT 1"}'
    assert reply.cost_usd == 0.001


def test_call_model_exhausts_retries_and_raises(monkeypatch):
    sleep_calls: list[float] = []
    monkeypatch.setattr(time, "sleep", lambda s: sleep_calls.append(s))

    def mock_completion(**kwargs):
        raise LiteRateLimitError(
            "rate limited", llm_provider="openrouter", model="test"
        )

    monkeypatch.setattr(litellm, "completion", mock_completion)

    with pytest.raises(
        RateLimitError,
        match="rate limit ou falha transitória persistente no OpenRouter",
    ):
        call_model([{"role": "user", "content": "hi"}], "test-model")

    assert len(sleep_calls) == 2


def test_cli_score_runs_and_prints_destination(tmp_path: Path, monkeypatch, capsys):
    experiment = _write_experiment(tmp_path / "exp")
    output_dir = experiment / "outputs" / "v1"
    output_dir.mkdir(parents=True)
    (output_dir / "one.txt").write_text('{"sql": "SELECT n FROM t"}', encoding="utf-8")

    monkeypatch.setattr(sys, "argv", ["prompt-lab", "score", str(experiment)])
    main()

    captured = capsys.readouterr()
    assert "results.json" in captured.out
    assert (experiment / "results.json").is_file()


def test_cli_missing_experiment_dir_fails(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        sys, "argv", ["prompt-lab", "score", str(tmp_path / "nonexistent")]
    )
    with pytest.raises(SystemExit):
        main()


def test_cli_missing_inputs_yaml_fails(tmp_path: Path, monkeypatch):
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    monkeypatch.setattr(sys, "argv", ["prompt-lab", "score", str(empty_dir)])
    with pytest.raises(SystemExit):
        main()
