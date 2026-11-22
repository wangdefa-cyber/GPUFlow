from __future__ import annotations

import streamlit as st

from gpu_sim.prototype.logic import preflight_tasks, simulation_readiness
from gpu_sim.prototype.state import get_scheduler, get_servers, get_tasks
from gpu_sim.prototype.ui import page_caption, section_header, source_badge


page_caption(
    "阶段 3 只验证仿真输入与页面交互。离散事件引擎将在阶段 4 接入，当前不会生成虚构的任务执行过程。"
)
source_badge("PROTOTYPE")

servers = get_servers()
tasks = get_tasks()
scheduler = get_scheduler()
checks = simulation_readiness(servers, tasks, scheduler)

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("仿真任务", len(tasks), border=True)
with col2:
    st.metric("活动服务器", sum(1 for row in servers if row.get("status") == "Active"), border=True)
with col3:
    st.metric("调度预设", scheduler.get("preset", "FIFO"), border=True)
with col4:
    st.metric("随机种子", scheduler.get("random_seed", 0), border=True)

section_header(
    "运行前检查",
    "输入来自当前会话的系统配置；真实历史工作负载回放将在阶段 4 加入。",
    icon=":material/rule:",
)
st.dataframe(
    checks,
    hide_index=True,
    width="stretch",
    alt="阶段 4 仿真运行前检查清单，包含集群、任务、容量、预检、调度配置和引擎状态",
)

if st.button("重新检查输入", icon=":material/refresh:", width="stretch", key="recheck_simulation"):
    st.toast("输入检查已重新计算。", icon=":material/check_circle:")

st.button(
    "开始仿真（阶段 4 启用）",
    icon=":material/play_arrow:",
    type="primary",
    width="stretch",
    disabled=True,
    help="离散事件引擎尚未实现，禁用按钮用于明确阶段边界。",
)

section_header(
    "当前任务可容纳性",
    "静态预检只比较单任务需求与单服务器容量，不模拟并发占用。",
    icon=":material/checklist:",
)
st.dataframe(
    preflight_tasks(tasks, servers),
    hide_index=True,
    width="stretch",
    alt="阶段 4 仿真任务在当前虚拟集群中的静态容量预检",
)

with st.container(border=True):
    st.markdown("**阶段 4 将替换本页的实现**")
    st.write(
        "实现事件队列、任务到达、等待队列、GPU/CPU/内存分配、完成事件、资源释放、暂停/继续/单步和确定性结果哈希。"
    )
    st.caption("页面播放速度只影响展示，不改变仿真时间线和指标。")
