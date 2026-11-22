from __future__ import annotations

import hashlib
import json

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from gpu_sim.application import execute_strategy_batch
from gpu_sim.db import get_database
from gpu_sim.prototype.ui import page_caption, section_header, source_badge
from gpu_sim.services import (
    database_counts,
    recent_runs,
    run_sample_rows,
    run_task_rows,
    scheduler_dicts,
)


METRIC_DEFS = {
    "average_wait_seconds": ("平均等待", "秒", 1.0),
    "average_turnaround_seconds": ("平均周转", "秒", 1.0),
    "makespan_seconds": ("Makespan", "秒", 1.0),
    "gpu_utilization": ("GPU 利用率", "%", 100.0),
    "cpu_utilization": ("CPU 利用率", "%", 100.0),
    "memory_utilization": ("内存利用率", "%", 100.0),
    "completion_rate": ("完成率", "%", 100.0),
    "timeout_rate": ("超时率", "%", 100.0),
    "fairness_index": ("公平性指数", "", 1.0),
}


def _compatibility_key(run) -> str:
    payload = {
        "tasks": run.task_snapshot_json,
        "servers": run.server_snapshot_json,
        "seed": run.random_seed,
        "sla": run.wait_sla_seconds,
        "skip": run.allow_skip_head,
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _format_metric(value, multiplier: float, digits: int = 2) -> str:
    if value is None:
        return "—"
    return f"{float(value) * multiplier:,.{digits}f}"


page_caption("在相同任务、集群、到达序列和种子下批量运行四种策略，比较指标、利用率曲线和完成时间分布。")
source_badge("SIMULATION")

database = get_database()
with database.session_scope() as session:
    counts = database_counts(session)
    configs = scheduler_dicts(session)
    recent = recent_runs(session, limit=40)

source_options: list[str] = []
if counts["user_tasks"]:
    source_options.append("用户创建任务")
if counts["historical_tasks"]:
    source_options.append("历史回放样本")
if not source_options:
    st.warning("当前没有可比较任务，请先创建用户任务或导入历史样本。", icon=":material/warning:")
    st.stop()

with st.container(border=True):
    st.markdown("**运行四策略批量实验**")
    st.caption("四个实验共享同一冻结任务/服务器快照和随机种子，只有排序/放置预设不同。")
    with st.form("strategy_batch_form"):
        batch_name = st.text_input("实验批次名称", value="策略批量对比")
        source_label = st.selectbox("工作负载", source_options, key="compare_source")
        default_config = next((row for row in configs if row["is_default"]), configs[0])
        seed = st.number_input(
            "随机种子",
            min_value=0,
            value=int(default_config["random_seed"]),
            key="compare_seed",
        )
        sla = st.number_input(
            "等待 SLA 秒",
            min_value=0,
            value=int(default_config["wait_sla_seconds"]),
            step=60,
            key="compare_sla",
        )
        skip = st.toggle("允许跳过队头", value=False, key="compare_skip")
        submitted = st.form_submit_button(
            "运行 FIFO / SJF / Priority / Best Fit",
            icon=":material/compare_arrows:",
            type="primary",
            width="stretch",
        )
        if submitted:
            source = "USER_CREATED" if source_label == "用户创建任务" else "HISTORICAL_REPLAY"
            presets = [name for name in ["FIFO", "SJF", "Priority", "Best Fit"] if name in {row["preset"] for row in configs}]
            try:
                with st.spinner("正在运行四种调度策略…"):
                    batch = execute_strategy_batch(
                        database=database,
                        source=source,
                        presets=presets,
                        random_seed=int(seed),
                        wait_sla_seconds=int(sla),
                        allow_skip_head=bool(skip),
                        name_prefix=batch_name,
                    )
                st.session_state.comparison_run_ids = [outcome.run_id for outcome in batch.outcomes]
                st.toast("四策略批量实验已完成。", icon=":material/check_circle:")
                st.rerun()
            except Exception as exc:
                st.error(str(exc), icon=":material/error:")

with database.session_scope() as session:
    recent = recent_runs(session, limit=40)

if not recent:
    st.info("尚无仿真实验。运行批量实验后即可比较。", icon=":material/info:")
    st.stop()

run_labels = {
    run.id: f"{run.name} · {run.workload_label} · {run.started_at:%m-%d %H:%M:%S}"
    for run in recent
}
preselected = [run_id for run_id in st.session_state.get("comparison_run_ids", []) if run_id in run_labels]
selected_ids = st.multiselect(
    "选择兼容实验",
    options=list(run_labels),
    default=preselected,
    format_func=lambda key: run_labels[key],
    help="至少选择两个实验；系统会校验任务、服务器、种子和 SLA 是否一致。",
)
if len(selected_ids) < 2:
    st.caption("至少选择两个实验后显示对比结果。")
    st.stop()

with database.session_scope() as session:
    selected_runs = [session.get(type(recent[0]), run_id) for run_id in selected_ids]
    selected_runs = [run for run in selected_runs if run is not None]
    run_tasks = {run.id: run_task_rows(session, run.id) for run in selected_runs}
    run_samples = {run.id: run_sample_rows(session, run.id) for run in selected_runs}

keys = {_compatibility_key(run) for run in selected_runs}
if len(keys) != 1:
    st.error("所选实验输入不一致，不能直接比较。请选择同一批次或相同任务、集群、种子和 SLA 的实验。", icon=":material/error:")
    compatibility = pd.DataFrame(
        [
            {
                "实验": run.name,
                "任务集合键": _compatibility_key(run)[:12],
                "预设": run.scheduler_preset,
                "种子": run.random_seed,
            }
            for run in selected_runs
        ]
    )
    st.dataframe(compatibility, hide_index=True, width="stretch", alt="所选实验输入兼容性检查")
    st.stop()

st.success("兼容性检查通过：任务、服务器、随机种子和等待 SLA 一致。", icon=":material/check_circle:")

section_header("指标对比", "所有百分比均按原始指标乘 100 展示。", icon=":material/analytics:")
rows = []
for metric, (label, unit, multiplier) in METRIC_DEFS.items():
    row = {"指标": label, "单位": unit}
    for run in selected_runs:
        row[run.scheduler_preset] = _format_metric(run.metrics_json.get(metric), multiplier)
    rows.append(row)
metrics_table = pd.DataFrame(rows)
st.dataframe(metrics_table, hide_index=True, width="stretch", alt="多种调度策略在同条件实验下的评价指标对比")

metric_choice = st.selectbox(
    "选择柱状图指标",
    options=list(METRIC_DEFS),
    format_func=lambda key: METRIC_DEFS[key][0],
    key="comparison_metric_choice",
)
chart_rows = [
    {
        "策略": run.scheduler_preset,
        METRIC_DEFS[metric_choice][0]: (
            float(run.metrics_json.get(metric_choice) or 0)
            * METRIC_DEFS[metric_choice][2]
        ),
    }
    for run in selected_runs
]
chart_df = pd.DataFrame(chart_rows)
metric_label = METRIC_DEFS[metric_choice][0]
bar = px.bar(
    chart_df,
    x="策略",
    y=metric_label,
    color="策略",
    text_auto=".2f",
    title=f"{metric_label} 对比",
)
bar.update_layout(showlegend=False, margin=dict(l=20, r=20, t=50, b=20))
st.plotly_chart(bar, width="stretch", config={"displayModeBar": False}, alt=f"不同调度策略的{metric_label}柱状对比")

section_header("资源利用率曲线", "曲线来自每个实验的真实资源采样，按仿真时间对齐。", icon=":material/show_chart:")
util_figure = go.Figure()
for run in selected_runs:
    samples = run_samples[run.id]
    if not samples:
        continue
    util_figure.add_trace(
        go.Scatter(
            x=[sample.simulation_time for sample in samples],
            y=[
                sample.gpu_allocated / sample.gpu_capacity * 100
                if sample.gpu_capacity
                else 0
                for sample in samples
            ],
            mode="lines",
            name=run.scheduler_preset,
            line_shape="hv",
        )
    )
util_figure.update_layout(
    xaxis_title="仿真时间（秒）",
    yaxis_title="GPU 利用率（%）",
    margin=dict(l=20, r=20, t=20, b=20),
    legend_title="策略",
)
st.plotly_chart(util_figure, width="stretch", config={"displayModeBar": False}, alt="不同调度策略在仿真时间线上的 GPU 利用率曲线")

section_header("完成时间分布", "只统计已完成任务的周转时间；受阻任务单独显示在下方。", icon=":material/bar_chart:")
distribution = go.Figure()
for run in selected_runs:
    values = [
        row.turnaround_time
        for row in run_tasks[run.id]
        if row.status == "COMPLETED" and row.turnaround_time is not None
    ]
    if values:
        distribution.add_trace(
            go.Box(y=values, name=run.scheduler_preset, boxmean=True)
        )
distribution.update_layout(
    yaxis_title="周转时间（秒）",
    margin=dict(l=20, r=20, t=20, b=20),
    showlegend=False,
)
st.plotly_chart(distribution, width="stretch", config={"displayModeBar": False}, alt="不同调度策略的已完成任务周转时间分布")

section_header("结果解读", "以下结论只引用当前对比中的实际指标。", icon=":material/lightbulb:")
insights = []
lowest_wait = min(
    selected_runs,
    key=lambda run: run.metrics_json.get("average_wait_seconds")
    if run.metrics_json.get("average_wait_seconds") is not None
    else float("inf"),
)
lowest_makespan = min(
    selected_runs,
    key=lambda run: run.metrics_json.get("makespan_seconds")
    if run.metrics_json.get("makespan_seconds") is not None
    else float("inf"),
)
highest_gpu = max(
    selected_runs,
    key=lambda run: run.metrics_json.get("gpu_utilization") or 0,
)
highest_fairness = max(
    selected_runs,
    key=lambda run: run.metrics_json.get("fairness_index") or 0,
)
insights.append(
    f"平均等待最短：**{lowest_wait.scheduler_preset}**，"
    f"{_format_metric(lowest_wait.metrics_json.get('average_wait_seconds'), 1.0, 2)} 秒。"
)
insights.append(
    f"Makespan 最短：**{lowest_makespan.scheduler_preset}**，"
    f"{_format_metric(lowest_makespan.metrics_json.get('makespan_seconds'), 1.0, 2)} 秒。"
)
insights.append(
    f"GPU 平均利用率最高：**{highest_gpu.scheduler_preset}**，"
    f"{_format_metric(highest_gpu.metrics_json.get('gpu_utilization'), 100.0, 2)}%。"
)
insights.append(
    f"公平性指数最高：**{highest_fairness.scheduler_preset}**，"
    f"{_format_metric(highest_fairness.metrics_json.get('fairness_index'), 1.0, 4)}。"
)
for insight in insights:
    st.markdown(f"- {insight}")

with st.expander("查看实验元数据与结果哈希", icon=":material/fingerprint:"):
    metadata = pd.DataFrame(
        [
            {
                "实验": run.name,
                "策略": run.scheduler_preset,
                "排序": run.order_rule,
                "放置": run.placement_rule,
                "种子": run.random_seed,
                "任务数": run.task_count,
                "服务器数": run.server_count,
                "结果哈希": run.result_hash,
            }
            for run in selected_runs
        ]
    )
    st.dataframe(metadata, hide_index=True, width="stretch", alt="参与对比实验的策略、输入和结果哈希元数据")
