"""GPUFlow Streamlit prototype entry point."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from gpu_sim.db import get_database  # noqa: E402
from gpu_sim.services import initialize_database  # noqa: E402


st.set_page_config(
    page_title="GPUFlow",
    page_icon=":material/memory:",
    layout="wide",
    initial_sidebar_state="expanded",
)

initialize_database(get_database())

st.logo(str(PROJECT_ROOT / "assets" / "logo.svg"))

with st.sidebar:
    st.caption("GPU cluster resource intelligence")
    st.badge("阶段 3 · 可操作原型", color="blue")
    st.caption("真实历史数据只读 · 配置数据仅保存在当前会话")

page = st.navigation(
    {
        "总览": [
            st.Page(
                "app_pages/overview.py",
                title="系统总览",
                icon=":material/dashboard:",
                help="查看真实 GPU Trace 的数据规模、GPU 容量和历史任务状态，以及原型系统当前能力。",
            ),
            st.Page(
                "app_pages/data_center.py",
                title="数据中心",
                icon=":material/database:",
                help="查看七张真实历史表的审计结果，并导入真实历史工作负载样本到 SQLite。",
            ),
        ],
        "资源配置": [
            st.Page(
                "app_pages/resources.py",
                title="GPU 资源管理",
                icon=":material/memory:",
                help="新增、编辑、删除并校验虚拟 GPU 服务器配置。",
            ),
            st.Page(
                "app_pages/tasks.py",
                title="任务管理",
                icon=":material/checklist:",
                help="维护用户创建的仿真任务、资源需求和优先级。",
            ),
        ],
        "调度实验": [
            st.Page(
                "app_pages/scheduler.py",
                title="调度控制台",
                icon=":material/tune:",
                help="配置 FIFO、SJF、Priority 与 Best Fit 预设，并查看确定性排序和静态容量预检。",
            ),
            st.Page(
                "app_pages/simulation.py",
                title="动态仿真",
                icon=":material/play_arrow:",
                help="运行确定性离散事件仿真，查看动态资源时间线、任务甘特图、调度事件和评价指标。",
            ),
            st.Page(
                "app_pages/comparison.py",
                title="策略对比",
                icon=":material/compare_arrows:",
                help="展示多策略比较的指标口径和兼容性要求；实验数据将在阶段 5 接入。",
            ),
        ],
        "智能决策": [
            st.Page(
                "app_pages/ai_decision.py",
                title="AI 决策",
                icon=":material/smart_toy:",
                help="展示有证据边界的调度建议规则；规则引擎将在阶段 6 实现。",
            ),
        ],
        "系统": [
            st.Page(
                "app_pages/settings.py",
                title="设置与溯源",
                icon=":material/settings:",
                help="查看数据来源、环境版本、原型边界和可下载的会话配置。",
            ),
        ],
    },
    position="sidebar",
)

st.title(page.title, icon=page.icon if getattr(page, "icon", None) else None)
page.run()
