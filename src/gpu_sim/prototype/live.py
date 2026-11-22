"""Live steppable simulation controls for the Streamlit page."""

from __future__ import annotations

import streamlit as st

from gpu_sim.application import PreparedSimulation, persist_simulation_result, prepare_simulation
from gpu_sim.db import Database
from gpu_sim.services import database_counts, scheduler_dicts
from gpu_sim.simulation import EngineStep, SimulationEngine


LIVE_ENGINE = "live_engine"
LIVE_PREPARED = "live_prepared"
LIVE_PLAYING = "live_playing"
LIVE_SAVED = "live_saved"
LIVE_STEP = "live_engine_step"
LIVE_NAME = "live_run_name"


def _save_if_finished(database: Database) -> None:
    if st.session_state.get(LIVE_SAVED):
        return
    engine: SimulationEngine | None = st.session_state.get(LIVE_ENGINE)
    prepared: PreparedSimulation | None = st.session_state.get(LIVE_PREPARED)
    if engine is None or prepared is None or not engine.finished:
        return
    result = engine.result()
    persist_simulation_result(
        database,
        prepared,
        result,
        str(st.session_state.get(LIVE_NAME, "实时仿真")),
    )
    st.session_state[LIVE_SAVED] = True
    st.session_state[LIVE_PLAYING] = False
    st.session_state["selected_run_id"] = result.run_id


def _advance_one() -> None:
    engine: SimulationEngine | None = st.session_state.get(LIVE_ENGINE)
    if engine is None:
        return
    st.session_state[LIVE_STEP] = engine.step()


@st.fragment(run_every="1s")
def _live_status_fragment(database: Database) -> None:
    engine: SimulationEngine | None = st.session_state.get(LIVE_ENGINE)
    prepared: PreparedSimulation | None = st.session_state.get(LIVE_PREPARED)
    if engine is None or prepared is None:
        return

    if st.session_state.get(LIVE_PLAYING) and not engine.finished:
        st.session_state[LIVE_STEP] = engine.step()
        _save_if_finished(database)

    step: EngineStep | None = st.session_state.get(LIVE_STEP)
    if step is None:
        engine.initialize()
        step = EngineStep(
            simulation_time=min(task.submit_time for task in prepared.engine_input.tasks),
            finished=False,
            waiting_count=0,
            running_count=0,
            completed_count=0,
            blocked_count=0,
            gpu_allocated=0.0,
            cpu_allocated=0.0,
            memory_allocated_gb=0.0,
            new_event_count=0,
        )
        st.session_state[LIVE_STEP] = step

    st.caption(
        f"{prepared.workload_label} · {prepared.engine_input.scheduler.preset} · "
        f"结果哈希 {engine.result().result_hash[:12] if engine.finished else '运行中'}"
    )
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("仿真时间", f"{step.simulation_time:,.0f}s", border=True)
    with col2:
        st.metric("等待", step.waiting_count, border=True)
    with col3:
        st.metric("运行中", step.running_count, border=True)
    with col4:
        st.metric("已完成", step.completed_count, border=True)
    with col5:
        st.metric("受阻", step.blocked_count, border=True)
    progress = (step.completed_count + step.blocked_count) / prepared.task_count
    st.progress(min(1.0, max(0.0, progress)), text=f"任务处理进度 {progress:.1%}")
    st.caption(
        f"当前分配：GPU {step.gpu_allocated:.2f} · CPU {step.cpu_allocated:.2f} · "
        f"内存 {step.memory_allocated_gb:.1f} GB"
    )
    if step.finished:
        st.success("实时仿真已结束，结果已写入 SQLite。", icon=":material/check_circle:")
    elif st.session_state.get(LIVE_PLAYING):
        st.badge("自动推进中", color="blue")
    else:
        st.badge("已暂停", color="gray")


def _reset_live() -> None:
    for key in (LIVE_ENGINE, LIVE_PREPARED, LIVE_PLAYING, LIVE_SAVED, LIVE_STEP, LIVE_NAME):
        st.session_state.pop(key, None)


def render_live_controls(database: Database) -> None:
    """Render pause/resume/step/reset controls using the real engine."""
    with st.expander("实时步进控制", expanded=LIVE_ENGINE in st.session_state):
        with database.session_scope() as session:
            counts = database_counts(session)
            configs = scheduler_dicts(session)
        source_options: list[str] = []
        if counts["user_tasks"]:
            source_options.append("用户创建任务")
        if counts["historical_tasks"]:
            source_options.append("历史回放样本")
        if not source_options:
            st.warning("没有可运行任务。", icon=":material/warning:")
            return

        with st.form("live_simulation_form"):
            name = st.text_input("实时实验名称", value="实时调度实验", key="live_name_input")
            source_label = st.selectbox("实时工作负载", source_options, key="live_source_input")
            preset_names = [row["preset"] for row in configs]
            preset = st.selectbox("实时调度预设", preset_names, key="live_preset_input")
            col1, col2 = st.columns(2)
            with col1:
                seed = st.number_input("实时随机种子", min_value=0, value=20261122, key="live_seed_input")
            with col2:
                sla = st.number_input("实时等待 SLA", min_value=0, value=900, step=60, key="live_sla_input")
            skip = st.toggle("允许跳过队头", value=False, key="live_skip_input")
            if st.form_submit_button("创建实时仿真", icon=":material/add_circle:", width="stretch"):
                source = "USER_CREATED" if source_label == "用户创建任务" else "HISTORICAL_REPLAY"
                try:
                    prepared = prepare_simulation(
                        database,
                        source=source,
                        preset=preset,
                        random_seed=int(seed),
                        wait_sla_seconds=int(sla),
                        allow_skip_head=bool(skip),
                    )
                    st.session_state[LIVE_PREPARED] = prepared
                    engine = SimulationEngine(prepared.engine_input)
                    engine.initialize()
                    st.session_state[LIVE_ENGINE] = engine
                    st.session_state[LIVE_PLAYING] = False
                    st.session_state[LIVE_SAVED] = False
                    st.session_state[LIVE_STEP] = None
                    st.session_state[LIVE_NAME] = name
                except Exception as exc:
                    st.error(str(exc), icon=":material/error:")

        if LIVE_ENGINE not in st.session_state:
            st.caption("创建后可继续、暂停、单步推进或直接运行到结束。")
            return

        controls = st.columns(4)
        with controls[0]:
            if st.button("开始 / 继续", icon=":material/play_arrow:", width="stretch", key="live_continue"):
                st.session_state[LIVE_PLAYING] = True
        with controls[1]:
            if st.button("暂停", icon=":material/pause:", width="stretch", key="live_pause"):
                st.session_state[LIVE_PLAYING] = False
        with controls[2]:
            if st.button("单步推进", icon=":material/skip_next:", width="stretch", key="live_step"):
                st.session_state[LIVE_PLAYING] = False
                _advance_one()
                _save_if_finished(database)
        with controls[3]:
            if st.button("重置", icon=":material/restart_alt:", width="stretch", key="live_reset"):
                _reset_live()

        if st.button("运行到结束并保存", icon=":material/fast_forward:", width="stretch", key="live_finish"):
            engine: SimulationEngine | None = st.session_state.get(LIVE_ENGINE)
            if engine is not None:
                st.session_state[LIVE_PLAYING] = False
                while not engine.finished:
                    st.session_state[LIVE_STEP] = engine.step()
                _save_if_finished(database)
                st.rerun()

        if LIVE_ENGINE in st.session_state:
            _live_status_fragment(database)
