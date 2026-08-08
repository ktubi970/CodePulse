from pathlib import Path
from streamlit.testing.v1 import AppTest


def test_demo_dashboard_shows_badge_warning_and_charts(monkeypatch: object) -> None:
    monkeypatch.setenv("CODEPULSE_DEMO", "1")  # type: ignore
    app = AppTest.from_file("dashboard/app.py")
    app.run(timeout=20)
    assert not app.exception
    assert any("ce corpus" in item.value.lower() for item in app.warning)
    assert len(app.get("plotly_chart")) >= 3
