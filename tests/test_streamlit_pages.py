from __future__ import annotations

import os
from pathlib import Path
from shutil import rmtree
from uuid import uuid4

from streamlit.testing.v1 import AppTest

from gpu_sim.advisor_service import generate_recommendations
from gpu_sim.application import execute_strategy_batch
from gpu_sim.db import get_database, reset_default_database_connection
from gpu_sim.services import initialize_database


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


def test_all_pages_render_with_real_simulation() -> None:
    test_dir = ROOT / "artifacts" / "test-pages" / uuid4().hex
    test_dir.mkdir(parents=True)
    os.environ["GPUFLOW_DB_PATH"] = str(test_dir / "gpuflow.db")
    reset_default_database_connection()
    try:
        database = get_database()
        initialize_database(database)
        batch = execute_strategy_batch(
            database=database,
            source="USER_CREATED",
            presets=["FIFO", "SJF", "Priority", "Best Fit"],
            random_seed=42,
            wait_sla_seconds=900,
            allow_skip_head=False,
            name_prefix="page smoke batch",
        )
        assert len(batch.outcomes) == 4
        generate_recommendations(database, batch.outcomes[0].run_id)

        at = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=60)
        at.session_state["comparison_run_ids"] = [
            item.run_id for item in batch.outcomes
        ]
        at = at.run()
        assert not at.exception, [exc.value for exc in at.exception]

        for path, title in PAGES:
            at = at.switch_page(path).run()
            assert not at.exception, f"{path}: {[exc.value for exc in at.exception]}"
            assert title in [item.value for item in at.title]
    finally:
        reset_default_database_connection()
        os.environ.pop("GPUFLOW_DB_PATH", None)
        rmtree(test_dir, ignore_errors=True)

def test_live_step_controls_advance_engine() -> None:
    from gpu_sim.application import prepare_simulation
    from gpu_sim.simulation import SimulationEngine

    test_dir = ROOT / "artifacts" / "test-live" / uuid4().hex
    test_dir.mkdir(parents=True)
    os.environ["GPUFLOW_DB_PATH"] = str(test_dir / "gpuflow.db")
    reset_default_database_connection()
    try:
        database = get_database()
        initialize_database(database)
        prepared = prepare_simulation(
            database,
            source="USER_CREATED",
            preset="FIFO",
            random_seed=42,
            wait_sla_seconds=900,
            allow_skip_head=False,
        )
        engine = SimulationEngine(prepared.engine_input)
        engine.initialize()

        at = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=60)
        at.session_state["live_prepared"] = prepared
        at.session_state["live_engine"] = engine
        at.session_state["live_playing"] = False
        at.session_state["live_saved"] = False
        at.session_state["live_engine_step"] = None
        at.session_state["live_run_name"] = "live smoke"
        at = at.run()
        at = at.switch_page("app_pages/simulation.py").run()
        assert not at.exception, [exc.value for exc in at.exception]

        step_button = next(button for button in at.button if button.label == "单步推进")
        at = step_button.click().run()
        assert not at.exception, [exc.value for exc in at.exception]
        assert at.session_state["live_engine_step"] is not None
    finally:
        reset_default_database_connection()
        os.environ.pop("GPUFLOW_DB_PATH", None)
        rmtree(test_dir, ignore_errors=True)
