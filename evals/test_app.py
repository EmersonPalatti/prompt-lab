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
