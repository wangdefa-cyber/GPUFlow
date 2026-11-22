from __future__ import annotations

import pandas as pd
import streamlit as st

from gpu_sim.db import get_database
from gpu_sim.prototype.logic import PRESETS
from gpu_sim.prototype.ui import page_caption, section_header, source_badge
from gpu_sim.services import scheduler_dicts, server_dicts, user_task_dicts


page_caption(
    "策略对比页定义统一评价口径和兼容性边界。真实对比将在阶段 5 基于已完成的仿真运行生成。"
)
source_badge("PROTOTYPE")

with get_database().session_scope() as session:
    servers = server_dicts(session)
    tasks = user_task_dicts(session)
    scheduler_configs = scheduler_dicts(session)
scheduler = next((row for row in scheduler_configs if row["is_default"]), scheduler_configs[0])

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("当前服务器", len(servers), border=True)
with col2:
    st.metric("当前任务", len(tasks), border=True)
with col3:
    st.metric("当前预设", scheduler.get("preset", "FIFO"), border=True)

section_header(
    "指标口径",
    "所有策略必须在相同任务集合、集群配置、到达序列和随机种子下比较。",
    icon=":material/analytics:",
)
metrics = pd.DataFrame(
    [
        {"指标": "平均等待时间", "定义": "已完成任务的开始时间减到达时间的均值", "单位": "秒"},
        {"指标": "平均周转时间", "定义": "已完成任务的完成时间减到达时间的均值", "单位": "秒"},
        {"指标": "Makespan", "定义": "最后完成时间减最早任务到达时间", "单位": "秒"},
        {"指标": "GPU 平均利用率", "定义": "已分配 GPU 时间积分除以容量与 Makespan 乘积", "单位": "%"},
        {"指标": "CPU 平均利用率", "定义": "已分配 CPU 时间积分除以容量与 Makespan 乘积", "单位": "%"},
        {"指标": "内存平均利用率", "定义": "已分配内存时间积分除以容量与 Makespan 乘积", "单位": "%"},
        {"指标": "完成率", "定义": "完成任务数除以全部实验任务数", "单位": "%"},
        {"指标": "超时率", "定义": "超过等待 SLA 或显式截止时间的任务比例", "单位": "%"},
        {"指标": "公平性指数", "定义": "按用户 GPU 分配量计算的 Jain 公平指数", "单位": "0–1"},
    ]
)
st.dataframe(metrics, hide_index=True, width="stretch", alt="阶段 2 定义的调度评价指标及公式口径")

section_header(
    "兼容性门槛",
    "不满足这些条件的实验不会被强行放在同一张对比表中。",
    icon=":material/rule:",
)
checks = pd.DataFrame(
    [
        {"条件": "数据集版本", "要求": "相同 dataset_version_id"},
        {"条件": "工作负载", "要求": "相同 workload_set_id 与任务到达序列"},
        {"条件": "集群配置", "要求": "相同 cluster_config_id"},
        {"条件": "随机种子", "要求": "确定性比较时相同 random_seed"},
        {"条件": "指标版本", "要求": "相同 formula_version"},
    ]
)
st.dataframe(checks, hide_index=True, width="stretch", alt="多调度策略实验进行直接比较前必须满足的输入兼容条件")

with st.container(border=True):
    st.markdown("**策略预设**")
    rows = [
        {
            "预设": value["label"],
            "排序规则": value["order_rule"],
            "放置规则": value["placement_rule"],
        }
        for value in PRESETS.values()
    ]
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch", alt="四种调度策略预设的排序与放置规则")
    st.caption("当前尚无可比较的仿真运行。阶段 5 将在此接入指标表、柱状图、利用率曲线和完成时间分布。")
