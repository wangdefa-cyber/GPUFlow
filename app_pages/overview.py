from __future__ import annotations

import streamlit as st

from gpu_sim.prototype import data_access
from gpu_sim.prototype.ui import format_int, page_caption, section_header, source_badge


page_caption(
    "以阿里巴巴真实 GPU Trace 为数据底座，连接资源配置、调度策略、离散事件仿真与效果评价。"
)
source_badge("HISTORICAL")

summary = data_access.dataset_summary()
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("真实历史记录", format_int(summary["total_rows"]), border=True)
with col2:
    st.metric("历史 GPU 容量", f"{summary['total_gpu']:,.0f}", "GPU 当量", border=True)
with col3:
    st.metric("历史作业", format_int(summary["job_rows"]), border=True)
with col4:
    st.metric("机器规格", format_int(summary["machine_count"]), "台", border=True)

section_header(
    "历史集群画像",
    "容量与状态来自已校验的七张官方表；图表展示真实历史聚合，不是仿真结果。",
    icon=":material/query_stats:",
)

left, right = st.columns(2)
with left:
    with st.container(border=True):
        st.markdown("**GPU 容量与机型构成**")
        capacity = data_access.gpu_capacity_by_type()
        st.bar_chart(
            capacity,
            x="gpu_type",
            y="GPU总量",
            x_label="GPU 型号",
            y_label="GPU 当量",
            alt="按 GPU 型号统计的真实历史机器 GPU 容量，P100 与 MISC 占比较高",
        )
        st.caption("来源：pai_machine_spec，真实历史机器规格。")

with right:
    with st.container(border=True):
        st.markdown("**历史作业状态分布**")
        status = data_access.categorical_distribution("pai_job_table", "status")
        st.bar_chart(
            status,
            x="分类",
            y="数量",
            x_label="作业状态",
            y_label="作业数",
            alt="真实历史作业状态分布，Terminated 最多，其次为 Failed",
        )
        st.caption("来源：pai_job_table，真实历史作业状态。")

section_header(
    "核心能力进度",
    "阶段 3 提供可操作原型；仿真与比价结果不会被提前伪造。",
    icon=":material/route:",
)

capabilities = st.columns(4)
with capabilities[0]:
    with st.container(border=True):
        st.markdown("**:material/database: 数据底座**")
        st.badge("已完成", color="green")
        st.write("七表校验、数据字典、质量问题与关联覆盖均已形成。")
with capabilities[1]:
    with st.container(border=True):
        st.markdown("**:material/tune: 调度设计**")
        st.badge("设计完成", color="blue")
        st.write("排序规则与放置规则分离，四种策略预设已明确。")
with capabilities[2]:
    with st.container(border=True):
        st.markdown("**:material/play_arrow: 仿真引擎**")
        st.badge("阶段 4", color="orange")
        st.write("将实现离散事件推进、资源分配和确定性回放。")
with capabilities[3]:
    with st.container(border=True):
        st.markdown("**:material/smart_toy: AI 建议**")
        st.badge("阶段 6", color="gray")
        st.write("只基于真实指标和事件提出可追溯建议。")

st.caption(
    "当前页面只展示真实历史聚合与系统配置原型；尚无仿真运行，因此不展示虚构利用率、等待时间或策略胜负。"
)
