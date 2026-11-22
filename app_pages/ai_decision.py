from __future__ import annotations

import pandas as pd
import streamlit as st

from gpu_sim.advisor_service import (
    accept_recommendation,
    apply_scheduler_hint,
    generate_recommendations,
    list_recommendations,
)
from gpu_sim.db import get_database
from gpu_sim.prototype.ui import page_caption, section_header, source_badge
from gpu_sim.services import recent_runs


SEVERITY_COLOR = {"high": "red", "medium": "orange", "low": "yellow", "info": "blue"}

page_caption("基于已完成仿真运行的真实指标、任务结果和事件生成规则建议；所有建议都带证据引用。")
source_badge("SIMULATION")

database = get_database()
with database.session_scope() as session:
    runs = recent_runs(session, limit=30)

if not runs:
    st.info("尚无仿真实验。请先在动态仿真或策略对比页运行实验。", icon=":material/info:")
    st.stop()

run_labels = {
    run.id: f"{run.name} · {run.scheduler_preset} · {run.workload_label} · {run.started_at:%m-%d %H:%M}"
    for run in runs
}
selected_run_id = st.selectbox(
    "选择实验运行",
    list(run_labels),
    format_func=lambda key: run_labels[key],
    key="advisor_run_id",
)

with database.session_scope() as session:
    selected_run = session.get(type(runs[0]), selected_run_id)

assert selected_run is not None
metrics = selected_run.metrics_json or {}
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("调度预设", selected_run.scheduler_preset, border=True)
with col2:
    wait = metrics.get("average_wait_seconds")
    st.metric("平均等待", "—" if wait is None else f"{wait:,.1f}", "秒", border=True)
with col3:
    util = metrics.get("gpu_utilization")
    st.metric("GPU 利用率", "—" if util is None else f"{util * 100:.1f}", "%", border=True)
with col4:
    blocked = metrics.get("blocked_tasks") or 0
    st.metric("受阻任务", f"{blocked:.0f}", border=True)

if st.button("生成规则建议", icon=":material/auto_awesome:", type="primary", width="stretch", key="generate_advice"):
    try:
        generate_recommendations(database, selected_run_id)
        st.toast("规则建议已生成并保存。", icon=":material/check_circle:")
        st.rerun()
    except Exception as exc:
        st.error(str(exc), icon=":material/error:")

recommendations = list_recommendations(database, selected_run_id)
if not recommendations:
    st.caption("该实验尚未生成建议。点击上方按钮执行规则引擎。")
    st.stop()

section_header("建议列表", "建议只读分析和候选配置，不会自动改变当前调度结果。", icon=":material/lightbulb:")
for index, recommendation in enumerate(recommendations, start=1):
    with st.container(border=True):
        top1, top2 = st.columns([5, 1])
        with top1:
            st.markdown(f"**{index}. {recommendation.summary}**")
        with top2:
            st.badge(
                recommendation.severity.upper(),
                color=SEVERITY_COLOR.get(recommendation.severity, "gray"),
            )
        st.write(recommendation.reasoning)
        st.caption(
            f"类型：{recommendation.recommendation_type} · 规则版本："
            f"{recommendation.rule_version} · 状态：{'已采纳' if recommendation.accepted else '待确认'}"
        )

        evidence_rows = []
        for evidence in recommendation.evidence_json:
            if evidence.get("kind") == "RUN_METRIC":
                evidence_rows.append(
                    {
                        "证据类型": "运行指标",
                        "引用": f"{evidence.get('run_id')} / {evidence.get('metric_name')}",
                        "值": evidence.get("value"),
                        "单位": evidence.get("unit", ""),
                    }
                )
            else:
                evidence_rows.append(
                    {
                        "证据类型": "任务结果",
                        "引用": f"{evidence.get('task_id')} / {evidence.get('task_name')}",
                        "值": evidence.get("status"),
                        "单位": (
                            f"等待 {evidence.get('wait_time')}s · "
                            f"GPU {evidence.get('gpu_required')} · "
                            f"{evidence.get('gpu_type_required') or '任意'}"
                        ),
                    }
                )
        st.dataframe(
            pd.DataFrame(evidence_rows),
            hide_index=True,
            width="stretch",
            alt="该条调度建议引用的真实指标或任务证据",
        )
        st.json(recommendation.suggested_patch_json, expanded=False)

        hint = recommendation.suggested_patch_json.get("scheduler_preset_hint")
        action_col1, action_col2 = st.columns([1, 1])
        with action_col1:
            if hint and not recommendation.accepted:
                if st.button(
                    f"采用 {hint} 调度预设",
                    icon=":material/check:",
                    width="stretch",
                    key=f"apply_preset_{recommendation.id}",
                ):
                    try:
                        applied = apply_scheduler_hint(database, recommendation.id)
                        st.toast(f"默认调度预设已更新为 {applied}。", icon=":material/check_circle:")
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc), icon=":material/error:")
            elif not recommendation.accepted:
                if st.button(
                    "标记为已采纳",
                    icon=":material/check:",
                    width="stretch",
                    key=f"accept_{recommendation.id}",
                ):
                    accept_recommendation(database, recommendation.id)
                    st.rerun()
        with action_col2:
            st.caption("容量类建议需要在 GPU 资源管理中人工修改配置，系统不会自动扩容。")

st.info(
    "当前使用规则引擎 advisor-rules-v1，不调用外部大模型。后续接入大模型时必须继续沿用同一证据结构。",
    icon=":material/info:",
)
