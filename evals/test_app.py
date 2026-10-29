from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py"


def test_app_loads_and_has_versions():
    app = AppTest.from_file(str(APP), default_timeout=40)
    app.run()

    assert not app.exception
    assert app.dataframe
    assert app.radio
    labels = list(app.radio[0].options)
    assert "v1" in labels
    assert "v2" in labels
    assert "v3" in labels


def test_app_switch_version_shows_diff_and_case_details():
    app = AppTest.from_file(str(APP), default_timeout=40)
    app.run()
    assert not app.exception

    # Initially on v1 (index 0), diff is not rendered
    diff_blocks_v1 = [c for c in app.code if c.language == "diff"]
    assert len(diff_blocks_v1) == 0

    # Switch to version v2
    app.radio[0].set_value("v2").run()
    assert not app.exception

    # Diff block should now be rendered
    diff_blocks_v2 = [c for c in app.code if c.language == "diff"]
    assert len(diff_blocks_v2) == 1
    assert "versão v1" in diff_blocks_v2[0].value or "---" in diff_blocks_v2[0].value

    # First dataframe remains the metrics accuracy table
    assert len(app.dataframe) >= 3
    # Case status and telemetry displayed in markdown
    assert any("Latência:" in m.value for m in app.markdown)
    assert any("Tokens:" in m.value for m in app.markdown)


def test_app_switch_experiment_to_cleaning():
    app = AppTest.from_file(str(APP), default_timeout=40)
    app.run()
    assert not app.exception

    # Switch experiment to 002-data-cleaning
    app.selectbox[0].set_value("002-data-cleaning").run()
    assert not app.exception

    # Verify cleaning experiment loaded
    assert app.selectbox[0].value == "002-data-cleaning"
    labels = list(app.radio[0].options)
    assert "v1" in labels
    assert "v2" in labels
    assert "v3" not in labels

    # First dataframe is the accuracy metrics table for cleaning
    assert len(app.dataframe) >= 1
