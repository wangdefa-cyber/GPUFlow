from __future__ import annotations

import json
from importlib.metadata import version

import pandas as pd
import streamlit as st

from gpu_sim.prototype.state import get_scheduler, get_servers, get_tasks, reset_state
from gpu_sim.prototype.ui import page_caption, section_header, source_badge


page_caption(
    "查看数据来源、运行环境和原型边界。会话配置可以下载，原始历史数据始终只读。"
)
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
st.dataframe(versions, hide_index=True, width="stretch", alt="GPUFlow 原型当前 Python 与主要依赖版本")

section_header(
    "数据来源",
    "真实历史数据、系统配置数据和仿真生成数据必须可区分。",
    icon=":material/link:",
)
sources = pd.DataFrame(
    [
        {"类别": "真实历史数据", "来源": "data/ 下七张官方 CSV", "状态": "只读，已校验 SHA-256"},
        {"类别": "系统配置数据", "来源": "当前 Streamlit 会话", "状态": "可编辑，阶段 4 持久化"},
        {"类别": "仿真生成数据", "来源": "阶段 4 离散事件引擎", "状态": "尚未生成"},
        {"类别": "AI 建议", "来源": "阶段 6 规则/模型", "状态": "尚未生成"},
    ]
)
st.dataframe(sources, hide_index=True, width="stretch", alt="真实历史、系统配置、仿真生成和 AI 建议的数据来源与状态")

configuration = {
    "servers": get_servers(),
    "tasks": get_tasks(),
    "scheduler": get_scheduler(),
}
st.download_button(
    "下载当前会话配置",
    data=json.dumps(configuration, ensure_ascii=False, indent=2),
    file_name="gpuflow_prototype_config.json",
    mime="application/json",
    icon=":material/download:",
    width="stretch",
    help="下载系统配置数据；不包含原始历史 CSV。",
)

if st.button("重置全部原型配置", icon=":material/restart_alt:", width="stretch", key="reset_all_settings"):
    reset_state()
    st.success("原型配置已恢复为示范状态。", icon=":material/check_circle:")

st.caption(
    "当前原型不使用登录、外部 API 密钥或持久化业务数据库。阶段 4 会引入 SQLite 并继续隔离三类数据。"
)
