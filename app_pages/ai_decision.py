from __future__ import annotations

import pandas as pd
import streamlit as st

from gpu_sim.prototype.state import get_scheduler, get_servers, get_tasks
from gpu_sim.prototype.ui import page_caption, section_header, source_badge


page_caption(
    "AI 辅助决策只读取真实指标、仿真事件和配置，不直接修改调度结果。本阶段先固定建议边界与证据格式。"
)
source_badge("PROTOTYPE")

servers = get_servers()
tasks = get_tasks()
scheduler = get_scheduler()

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("可分析服务器", len(servers), border=True)
with col2:
    st.metric("可分析任务", len(tasks), border=True)
with col3:
    st.metric("规则版本", "ai-rules-v1", border=True)

section_header(
    "规则目录",
    "阶段 6 将基于这些规则生成有证据的建议；当前不输出虚构的自然语言结论。",
    icon=":material/smart_toy:",
)
rules = pd.DataFrame(
    [
        {"规则": "拥堵预警", "触发依据": "等待队列持续增长且 GPU 利用率较高", "建议": "增加同型号 GPU 或调整任务到达节奏"},
        {"规则": "资源碎片", "触发依据": "总空闲 GPU 足够但大任务无法放置", "建议": "检查服务器分组与 Best Fit 放置效果"},
        {"规则": "容量错配", "触发依据": "某型号 GPU 长期不足或长期闲置", "建议": "调整服务器型号比例"},
        {"规则": "优先级饥饿", "触发依据": "高优先级任务等待超过 SLA", "建议": "检查 Priority 预设或预留资源"},
        {"规则": "策略推荐", "触发依据": "相同输入下多策略指标差异稳定", "建议": "选择等待、Makespan、公平性综合更优的预设"},
    ]
)
st.dataframe(rules, hide_index=True, width="stretch", alt="AI 辅助决策模块的规则目录、触发依据和建议范围")

section_header(
    "证据要求",
    "每条建议必须绑定可复查引用；没有证据时返回“无法判断”。",
    icon=":material/policy:",
)
evidence = pd.DataFrame(
    [
        {"证据类型": "仿真运行", "示例": "run_id、输入哈希、随机种子"},
        {"证据类型": "指标", "示例": "指标名称、值、公式版本"},
        {"证据类型": "事件", "示例": "等待、调度、完成事件的 sequence_no"},
        {"证据类型": "配置", "示例": "cluster_config_id、scheduler_config_id"},
    ]
)
st.dataframe(evidence, hide_index=True, width="stretch", alt="AI 建议必须引用的仿真运行、指标、事件和配置证据")

st.info(
    "当前没有完整的仿真运行，因此不能生成实际调度建议。阶段 6 会先实现规则引擎，再评估是否接入外部大模型。",
    icon=":material/info:",
)

with st.container(border=True):
    st.markdown("**当前上下文预览**")
    st.write(
        f"调度预设：{scheduler.get('preset', 'FIFO')} · "
        f"服务器：{len(servers)} 台 · 任务：{len(tasks)} 条 · "
        f"等待 SLA：{scheduler.get('wait_sla_seconds', 0)} 秒"
    )
    st.caption("该上下文来自系统配置数据，不能用于计算真实 GPU 利用率或历史结论。")
