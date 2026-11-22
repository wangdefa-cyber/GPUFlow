from __future__ import annotations

import pandas as pd
import streamlit as st

from gpu_sim.db import get_database
from gpu_sim.prototype.logic import GPU_TYPES, SERVER_STATUSES, capacity_summary, validate_servers
from gpu_sim.services import replace_servers, reset_servers_to_defaults, server_dicts
from gpu_sim.prototype.ui import page_caption, section_header, source_badge


page_caption(
    "维护 SQLite 中用户自定义的虚拟 GPU 服务器。历史 machine_spec 只作为参考，不会被修改。"
)
source_badge("CONFIG")

database = get_database()
st.session_state.setdefault("server_editor_version", 1)
with database.session_scope() as session:
    servers = server_dicts(session)

summary = capacity_summary(servers)
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("服务器", summary.server_count, f"{summary.active_server_count} 台活动", border=True)
with col2:
    st.metric("GPU 容量", f"{summary.total_gpu:g}", "GPU 当量", border=True)
with col3:
    st.metric("CPU 容量", f"{summary.total_cpu:g}", "核", border=True)
with col4:
    st.metric("内存容量", f"{summary.total_memory_gb:g}", "GB", border=True)

section_header(
    "服务器配置",
    "支持新增、编辑和删除行；保存后写入 SQLite，已有实验保留冻结快照。",
    icon=":material/dns:",
)

df = pd.DataFrame(servers)
edited = st.data_editor(
    df,
    key=f"servers_editor_{st.session_state.server_editor_version}",
    hide_index=True,
    width="stretch",
    num_rows="dynamic",
    column_order=[
        "id", "name", "gpu_type", "gpu_capacity", "cpu_capacity",
        "memory_capacity_gb", "status",
    ],
    disabled=["id"],
    column_config={
        "id": st.column_config.TextColumn("服务器 ID", help="新行会自动生成 ID"),
        "name": st.column_config.TextColumn("服务器名称", required=True),
        "gpu_type": st.column_config.SelectboxColumn("GPU 型号", options=list(GPU_TYPES), required=True),
        "gpu_capacity": st.column_config.NumberColumn("GPU 容量", min_value=0.0, step=0.5, format="%.1f"),
        "cpu_capacity": st.column_config.NumberColumn("CPU 核数", min_value=0.0, step=4.0, format="%.0f"),
        "memory_capacity_gb": st.column_config.NumberColumn("内存 GB", min_value=0.0, step=16.0, format="%.0f"),
        "status": st.column_config.SelectboxColumn("状态", options=list(SERVER_STATUSES), required=True),
    },
    alt="可编辑的虚拟 GPU 服务器配置表",
)

button_col1, button_col2 = st.columns([1, 1])
with button_col1:
    if st.button("保存服务器配置", icon=":material/save:", width="stretch", key="save_servers"):
        records = edited.to_dict("records")
        errors = validate_servers(records)
        if errors:
            st.error(errors[0], icon=":material/error:")
            with st.expander("查看全部校验错误"):
                for error in errors:
                    st.write(f"- {error}")
        else:
            with database.session_scope() as session:
                replace_servers(session, records)
            st.session_state.server_editor_version += 1
            st.toast("服务器配置已写入 SQLite。", icon=":material/check_circle:")
            st.rerun()
with button_col2:
    if st.button("恢复示范配置", icon=":material/restart_alt:", width="stretch", key="reset_servers"):
        with database.session_scope() as session:
            reset_servers_to_defaults(session)
        st.session_state.server_editor_version += 1
        st.toast("服务器配置已恢复为示范数据。", icon=":material/restart_alt:")
        st.rerun()

view = edited.copy()
if not view.empty:
    view["gpu_capacity"] = pd.to_numeric(view["gpu_capacity"], errors="coerce").fillna(0)
    by_type = (
        view.groupby("gpu_type", as_index=False)["gpu_capacity"]
        .sum()
        .sort_values("gpu_capacity", ascending=False)
    )
    with st.container(border=True):
        st.markdown("**按 GPU 型号汇总容量**")
        st.bar_chart(
            by_type,
            x="gpu_type",
            y="gpu_capacity",
            x_label="GPU 型号",
            y_label="配置容量（GPU 当量）",
            alt="当前 SQLite 虚拟 GPU 集群按型号汇总的配置容量",
        )
        st.caption("来源：系统配置数据（SQLite）。")

st.caption("资源分配约束将在每次仿真运行中由引擎实时校验，超出容量的任务会保持等待或受阻状态。")
