from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]
PAGES = [
    ("app_pages/overview.py", "系统总览"),
    ("app_pages/data_center.py", "数据中心"),
    ("app_pages/resources.py", "GPU 资源管理"),
    ("app_pages/tasks.py", "任务管理"),
    ("app_pages/scheduler.py", "调度控制台"),
    ("app_pages/simulation.py", "动态仿真"),
    ("app_pages/comparison.py", "策略对比"),
    ("app_pages/ai_decision.py", "AI 决策"),
    ("app_pages/settings.py", "设置与溯源"),
]


def test_all_prototype_pages_render() -> None:
    at = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=60).run()
    assert not at.exception

    for path, title in PAGES:
        at = at.switch_page(path).run()
        assert not at.exception, f"{path}: {[exc.value for exc in at.exception]}"
        assert title in [item.value for item in at.title]
