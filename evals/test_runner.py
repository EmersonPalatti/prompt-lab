from pathlib import Path

from prompt_lab.runner import ModelReply, run_experiment


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
