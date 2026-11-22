from __future__ import annotations

import pandas as pd
import streamlit as st

from gpu_sim.prototype.logic import GPU_TYPES, validate_tasks
from gpu_sim.prototype.state import (
    editor_version,
    get_tasks,
    reset_state,
    save_tasks,
    tasks_frame,
)
from gpu_sim.prototype.ui import page_caption, section_header, source_badge


page_caption(
    "维护仿真任务及其 GPU、CPU、内存、优先级和预计运行时长。当前任务均为系统配置数据，不代表真实历史作业。"
)
source_badge("CONFIG")

tasks = get_tasks()
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("仿真任务", len(tasks), border=True)
with col2:
    st.metric("GPU 需求", f"{sum(float(row.get('gpu_required', 0)) for row in tasks):g}", "GPU 当量", border=True)
with col3:
    st.metric("CPU 需求", f"{sum(float(row.get('cpu_required', 0)) for row in tasks):g}", "核", border=True)
with col4:
    st.metric("平均优先级", f"{sum(int(row.get('priority', 0)) for row in tasks) / len(tasks):.1f}" if tasks else "—", border=True)

section_header(
    "仿真任务配置",
    "任务可以整体放置在一台服务器；首版不支持跨服务器拆分。",
    icon=":material/checklist:",
)

edited = st.data_editor(
    tasks_frame(),
    key=f"tasks_editor_{editor_version()}",
    hide_index=True,
    width="stretch",
    num_rows="dynamic",
    column_order=[
        "id",
        "name",
        "source_type",
        "gpu_required",
        "cpu_required",
        "memory_required_gb",
        "priority",
        "estimated_duration",
        "gpu_type_required",
        "submit_time",
    ],
    disabled=["id", "source_type"],
    column_config={
        "id": st.column_config.TextColumn("任务 ID"),
        "name": st.column_config.TextColumn("任务名称", required=True),
        "source_type": st.column_config.TextColumn("来源", help="当前原型只创建用户任务"),
        "gpu_required": st.column_config.NumberColumn("GPU 需求", min_value=0.0, step=0.5, format="%.1f"),
        "cpu_required": st.column_config.NumberColumn("CPU 需求", min_value=0.0, step=1.0, format="%.0f"),
        "memory_required_gb": st.column_config.NumberColumn("内存 GB", min_value=0.0, step=4.0, format="%.1f"),
        "priority": st.column_config.NumberColumn("优先级", min_value=0, max_value=100, step=1, format="%d"),
        "estimated_duration": st.column_config.NumberColumn("预计时长 秒", min_value=1.0, step=60.0, format="%.0f"),
        "gpu_type_required": st.column_config.TextColumn("GPU 型号要求", help="留空表示任意型号"),
        "submit_time": st.column_config.NumberColumn("到达时间 秒", min_value=0.0, step=60.0, format="%.0f"),
    },
    alt="可编辑的仿真任务配置表，包含资源需求、优先级、预计时长和到达时间",
)

button_col1, button_col2 = st.columns([1, 1])
with button_col1:
    if st.button("保存任务配置", icon=":material/save:", width="stretch", key="save_tasks"):
        records = edited.to_dict("records")
        errors = validate_tasks(records)
        if errors:
            st.error(errors[0], icon=":material/error:")
            with st.expander("查看全部校验错误"):
                for error in errors:
                    st.write(f"- {error}")
        else:
            save_tasks(records)
            st.success("任务配置已保存到当前会话。", icon=":material/check_circle:")
with button_col2:
    if st.button("恢复示范任务", icon=":material/restart_alt:", width="stretch", key="reset_tasks"):
        reset_state()
        st.rerun()

view = edited.copy()
view["gpu_required"] = pd.to_numeric(view["gpu_required"], errors="coerce").fillna(0)
view["gpu_type_required"] = view["gpu_type_required"].replace("", "任意")
by_type = (
    view.groupby("gpu_type_required", as_index=False)["gpu_required"]
    .sum()
    .sort_values("gpu_required", ascending=False)
)
with st.container(border=True):
    st.markdown("**按 GPU 型号汇总任务需求**")
    st.bar_chart(
        by_type,
        x="gpu_type_required",
        y="gpu_required",
        x_label="GPU 型号要求",
        y_label="GPU 需求（当量）",
        alt="当前系统配置任务按 GPU 型号汇总的需求量",
    )
    st.caption("来源：系统配置数据（当前浏览器会话），不是历史作业分布。")

st.caption(
    "阶段 4 将从历史实例构建工作负载集，并把来源标记为 HISTORICAL_REPLAY；用户创建任务保持 USER_CREATED。"
)
