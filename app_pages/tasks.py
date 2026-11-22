from __future__ import annotations

import pandas as pd
import streamlit as st

from gpu_sim.db import get_database
from gpu_sim.prototype.logic import validate_tasks
from gpu_sim.prototype.ui import page_caption, section_header, source_badge
from gpu_sim.services import replace_user_tasks, reset_user_tasks_to_defaults, task_dicts, user_task_dicts


page_caption("维护用户仿真任务，并查看从真实历史实例映射出的回放工作负载。")
source_badge("CONFIG")

database = get_database()
st.session_state.setdefault("task_editor_version", 1)
with database.session_scope() as session:
    user_tasks = user_task_dicts(session)
    historical_tasks, historical_dataset = task_dicts(session, "HISTORICAL_REPLAY")

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("用户任务", len(user_tasks), border=True)
with col2:
    st.metric("历史回放任务", len(historical_tasks), border=True)
with col3:
    st.metric(
        "用户 GPU 需求",
        f"{sum(float(row.get('gpu_required', 0)) for row in user_tasks):g}",
        "GPU 当量",
        border=True,
    )
with col4:
    average_priority = (
        sum(int(row.get("priority", 0)) for row in user_tasks) / len(user_tasks)
        if user_tasks
        else 0
    )
    st.metric("平均优先级", f"{average_priority:.1f}", border=True)

tabs = st.tabs(["用户任务", "历史回放样本"])

with tabs[0]:
    section_header(
        "用户任务配置",
        "任务写入 SQLite；首版一个任务只能整体放置在一台服务器。",
        icon=":material/checklist:",
    )
    user_df = pd.DataFrame(user_tasks)
    edited = st.data_editor(
        user_df,
        key=f"tasks_editor_{st.session_state.task_editor_version}",
        hide_index=True,
        width="stretch",
        num_rows="dynamic",
        column_order=[
            "id", "name", "source_type", "gpu_required", "cpu_required",
            "memory_required_gb", "priority", "estimated_duration",
            "gpu_type_required", "submit_time",
        ],
        disabled=["id", "source_type"],
        column_config={
            "id": st.column_config.TextColumn("任务 ID"),
            "name": st.column_config.TextColumn("任务名称", required=True),
            "source_type": st.column_config.TextColumn("来源"),
            "gpu_required": st.column_config.NumberColumn("GPU 需求", min_value=0.0, step=0.5, format="%.1f"),
            "cpu_required": st.column_config.NumberColumn("CPU 需求", min_value=0.0, step=1.0, format="%.0f"),
            "memory_required_gb": st.column_config.NumberColumn("内存 GB", min_value=0.0, step=4.0, format="%.1f"),
            "priority": st.column_config.NumberColumn("优先级", min_value=0, max_value=100, step=1, format="%d"),
            "estimated_duration": st.column_config.NumberColumn("预计时长 秒", min_value=1.0, step=60.0, format="%.0f"),
            "gpu_type_required": st.column_config.TextColumn("GPU 型号要求", help="留空表示任意型号"),
            "submit_time": st.column_config.NumberColumn("到达时间 秒", min_value=0.0, step=60.0, format="%.0f"),
        },
        alt="可编辑的 SQLite 用户仿真任务配置表",
    )

    button_col1, button_col2 = st.columns([1, 1])
    with button_col1:
        if st.button("保存用户任务", icon=":material/save:", width="stretch", key="save_tasks"):
            records = edited.to_dict("records")
            errors = validate_tasks(records)
            if errors:
                st.error(errors[0], icon=":material/error:")
                with st.expander("查看全部校验错误"):
                    for error in errors:
                        st.write(f"- {error}")
            else:
                with database.session_scope() as session:
                    replace_user_tasks(session, records)
                st.session_state.task_editor_version += 1
                st.toast("用户任务已写入 SQLite。", icon=":material/check_circle:")
                st.rerun()
    with button_col2:
        if st.button("恢复示范任务", icon=":material/restart_alt:", width="stretch", key="reset_tasks"):
            with database.session_scope() as session:
                reset_user_tasks_to_defaults(session)
            st.session_state.task_editor_version += 1
            st.toast("用户任务已恢复为示范数据。", icon=":material/restart_alt:")
            st.rerun()

    if not edited.empty:
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
                alt="当前 SQLite 用户任务按 GPU 型号汇总的需求量",
            )

with tabs[1]:
    if historical_dataset is None:
        st.info("尚未导入历史工作负载样本。请前往数据中心执行导入。", icon=":material/info:")
    else:
        st.caption(
            f"数据集：{historical_dataset.version_code} · 任务数：{historical_dataset.task_count} · "
            f"优先级来源：历史记录无优先级，统一中性值 5"
        )
        historical_df = pd.DataFrame(historical_tasks)
        st.dataframe(
            historical_df,
            hide_index=True,
            width="stretch",
            column_config={
                "gpu_required": st.column_config.NumberColumn("GPU 需求", format="%.2f"),
                "cpu_required": st.column_config.NumberColumn("CPU 需求", format="%.2f"),
                "memory_required_gb": st.column_config.NumberColumn("内存 GB", format="%.1f"),
                "estimated_duration": st.column_config.NumberColumn("真实实例时长 秒", format="%.0f"),
                "submit_time": st.column_config.NumberColumn("相对到达时间 秒", format="%.0f"),
            },
            alt="由真实历史实例和 task 资源计划映射出的只读回放任务",
        )
        st.caption("历史回放任务只读；如需修改，应创建新的用户任务或导入新的工作负载样本。")
