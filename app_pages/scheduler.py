from __future__ import annotations

import pandas as pd
import streamlit as st

from gpu_sim.prototype.logic import PRESETS, order_tasks, preflight_tasks
from gpu_sim.prototype.state import get_scheduler, get_servers, get_tasks, save_scheduler
from gpu_sim.prototype.ui import page_caption, section_header, source_badge


page_caption(
    "配置任务排序与服务器放置规则。本页显示确定性排序预览和静态容量预检，不执行动态资源分配。"
)
source_badge("CONFIG")

scheduler = get_scheduler()
preset_names = list(PRESETS)
current_index = preset_names.index(scheduler.get("preset", "FIFO")) if scheduler.get("preset") in PRESETS else 0
preset = st.radio("调度策略预设", preset_names, index=current_index, horizontal=True, key="scheduler_preset")

config = PRESETS[preset]
left, right = st.columns([1, 1])
with left:
    with st.container(border=True):
        st.markdown(f"**{config['label']} 预设**")
        st.write(config["description"])
        st.caption(f"排序规则：{config['order_rule']} · 放置规则：{config['placement_rule']}")
with right:
    st.metric("任务排序", config["order_rule"], border=True)
    st.metric("资源放置", config["placement_rule"], border=True)

with st.form("scheduler_config_form"):
    wait_sla = st.number_input(
        "等待 SLA（秒）",
        min_value=0,
        max_value=604800,
        value=int(scheduler.get("wait_sla_seconds", 900)),
        step=60,
        help="任务等待超过该值时计为超时；显式截止时间优先。",
    )
    random_seed = st.number_input(
        "随机种子",
        min_value=0,
        max_value=2_147_483_647,
        value=int(scheduler.get("random_seed", 20261122)),
        step=1,
        help="用于后续仿真和确定性抽样。",
    )
    allow_skip_head = st.toggle(
        "允许跳过队列头部任务",
        value=bool(scheduler.get("allow_skip_head", False)),
        help="首版默认关闭，避免提前改变 FIFO 的公平性语义。",
    )
    submitted = st.form_submit_button("保存调度配置", icon=":material/save:", width="stretch")
    if submitted:
        save_scheduler(
            {
                "preset": preset,
                "wait_sla_seconds": wait_sla,
                "random_seed": random_seed,
                "allow_skip_head": allow_skip_head,
            }
        )
        st.success("调度配置已保存到当前会话。", icon=":material/check_circle:")

tasks = get_tasks()
servers = get_servers()
ordered = order_tasks(tasks, preset)
order_rows = [
    {
        "顺序": index,
        "任务": task.get("name", ""),
        "到达时间 秒": float(task.get("submit_time", 0) or 0),
        "优先级": int(task.get("priority", 0) or 0),
        "预计时长 秒": float(task.get("estimated_duration", 0) or 0),
        "GPU 需求": float(task.get("gpu_required", 0) or 0),
        "GPU 型号": task.get("gpu_type_required") or "任意",
    }
    for index, task in enumerate(ordered, start=1)
]

section_header(
    "任务排序预览",
    "这里只验证所选排序规则的确定性顺序，不代表任务已经获得资源。",
    icon=":material/sort:",
)
st.dataframe(
    pd.DataFrame(order_rows),
    hide_index=True,
    width="stretch",
    column_config={
        "到达时间 秒": st.column_config.NumberColumn(format="%.0f"),
        "预计时长 秒": st.column_config.NumberColumn(format="%.0f"),
        "GPU 需求": st.column_config.NumberColumn(format="%.1f"),
    },
    alt="按当前调度预设生成的任务确定性排序预览",
)

section_header(
    "静态容量预检",
    "检查每个任务是否能被至少一台服务器容纳；这不是动态调度，也不存在资源时间重叠计算。",
    icon=":material/fact_check:",
)
preflight = pd.DataFrame(preflight_tasks(tasks, servers))
st.dataframe(
    preflight,
    hide_index=True,
    width="stretch",
    column_config={
        "GPU 需求": st.column_config.NumberColumn(format="%.1f"),
        "CPU 需求": st.column_config.NumberColumn(format="%.0f"),
        "内存需求 GB": st.column_config.NumberColumn(format="%.1f"),
    },
    alt="当前任务相对虚拟集群容量的静态可容纳性预检",
)
if not preflight.empty and (preflight["预检结果"] == "可容纳").all():
    st.success("全部任务均可由至少一台服务器容纳。", icon=":material/check_circle:")
else:
    st.warning("存在当前配置无法容纳的任务；阶段 4 会把它们保留在等待或不可调度状态。", icon=":material/warning:")

st.caption(
    "Best Fit 首版保持 FIFO 排序，只改变服务器放置规则；这样策略差异更容易解释。"
)
