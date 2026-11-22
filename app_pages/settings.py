from __future__ import annotations

import json
from importlib.metadata import version

import pandas as pd
import streamlit as st

from gpu_sim.db import get_database
from gpu_sim.prototype.ui import page_caption, section_header, source_badge
from gpu_sim.services import (
    reset_servers_to_defaults,
    reset_user_tasks_to_defaults,
    scheduler_dicts,
    server_dicts,
    user_task_dicts,
)


page_caption("查看数据来源、SQLite 状态和运行环境。系统配置可以下载，原始历史数据始终只读。")
source_badge("PROTOTYPE")

versions = pd.DataFrame(
    [
        {"组件": "Python", "版本": "3.11.18"},
        {"组件": "pandas", "版本": version("pandas")},
        {"组件": "numpy", "版本": version("numpy")},
        {"组件": "SQLAlchemy", "版本": version("sqlalchemy")},
        {"组件": "pytest", "版本": version("pytest")},
        {"组件": "plotly", "版本": version("plotly")},
        {"组件": "streamlit", "版本": version("streamlit")},
    ]
)
st.dataframe(versions, hide_index=True, width="stretch", alt="GPUFlow 当前 Python 与主要依赖版本")

section_header(
    "数据来源",
    "真实历史数据、系统配置数据和仿真生成数据必须可区分。",
    icon=":material/link:",
)
sources = pd.DataFrame(
    [
        {"类别": "真实历史数据", "来源": "data/ 下七张官方 CSV", "状态": "只读，已校验 SHA-256"},
        {"类别": "历史工作负载样本", "来源": "真实 instance + task 映射", "状态": "SQLite 只读回放任务"},
        {"类别": "系统配置数据", "来源": "用户任务与 GPU 服务器", "状态": "可编辑，SQLite 持久化"},
        {"类别": "仿真生成数据", "来源": "离散事件引擎", "状态": "实验、事件、任务结果和指标已持久化"},
        {"类别": "AI 建议", "来源": "阶段 6 规则/模型", "状态": "尚未生成"},
    ]
)
st.dataframe(sources, hide_index=True, width="stretch", alt="真实历史、系统配置、仿真生成和 AI 建议的数据来源与状态")

database = get_database()
with database.session_scope() as session:
    configuration = {
        "servers": server_dicts(session),
        "user_tasks": user_task_dicts(session),
        "scheduler_configs": scheduler_dicts(session),
    }

st.caption(f"SQLite 数据库：{database.path}")
st.download_button(
    "下载当前系统配置",
    data=json.dumps(configuration, ensure_ascii=False, indent=2),
    file_name="gpuflow_system_config.json",
    mime="application/json",
    icon=":material/download:",
    width="stretch",
    help="下载服务器、用户任务和调度配置；不包含原始历史 CSV 或仿真事件。",
)

if st.button("恢复服务器与用户任务示范配置", icon=":material/restart_alt:", width="stretch", key="reset_all_settings"):
    with database.session_scope() as session:
        reset_servers_to_defaults(session)
        reset_user_tasks_to_defaults(session)
    st.success("服务器与用户任务已恢复为示范状态；历史回放样本和实验记录保持不变。", icon=":material/check_circle:")

st.caption("外部 API 密钥应通过环境变量管理；当前阶段没有外部模型调用。")
