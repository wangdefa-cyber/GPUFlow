from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from gpu_sim.application import execute_simulation
from gpu_sim.db import get_database
from gpu_sim.prototype.live import render_live_controls
from gpu_sim.prototype.ui import page_caption, section_header, source_badge
from gpu_sim.services import (
    database_counts,
    recent_runs,
    run_event_rows,
    run_sample_rows,
    run_task_rows,
    scheduler_dicts,
)


METRIC_LABELS = {
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


def _metric_text(value: float | None, multiplier: float, digits: int = 1) -> str:
    if value is None:
        return "—"
    return f"{value * multiplier:,.{digits}f}"


page_caption("使用真实 SQLite 配置和历史回放任务运行确定性离散事件仿真，并查看甘特图、时间线与指标。")
source_badge("SIMULATION")

database = get_database()
with database.session_scope() as session:
    counts = database_counts(session)
    configs = scheduler_dicts(session)
    recent = recent_runs(session, limit=20)

source_options: list[str] = []
if counts["user_tasks"]:
    source_options.append("用户创建任务")
if counts["historical_tasks"]:
    source_options.append("历史回放样本")
if not source_options:
    st.warning("当前没有可运行任务，请先在任务管理中创建任务或从数据中心导入历史样本。", icon=":material/warning:")
    st.stop()

render_live_controls(database)

with st.form("run_simulation_form"):
    run_name = st.text_input("实验名称", value=f"调度实验 {counts['runs'] + 1}", key="run_name")
    source_label = st.selectbox("工作负载", source_options, key="run_source")
    preset_names = [row["preset"] for row in configs]
    default_config = next((row for row in configs if row["is_default"]), configs[0])
    preset = st.selectbox(
        "调度预设",
        preset_names,
        index=preset_names.index(default_config["preset"]),
        key="run_preset",
    )
    selected_preset = next(row for row in configs if row["preset"] == preset)
    col1, col2, col3 = st.columns(3)
    with col1:
        random_seed = st.number_input(
            "随机种子",
            min_value=0,
            max_value=2_147_483_647,
            value=int(selected_preset["random_seed"]),
            key="run_seed",
        )
    with col2:
        wait_sla = st.number_input(
            "等待 SLA 秒",
            min_value=0,
            max_value=604800,
            value=int(selected_preset["wait_sla_seconds"]),
            step=60,
            key="run_sla",
        )
    with col3:
        allow_skip_head = st.toggle(
            "允许跳过队头",
            value=bool(selected_preset["allow_skip_head"]),
            key="run_skip_head",
        )
    submitted = st.form_submit_button(
        "运行离散事件仿真",
        icon=":material/play_arrow:",
        type="primary",
        width="stretch",
    )
    if submitted:
        source = "USER_CREATED" if source_label == "用户创建任务" else "HISTORICAL_REPLAY"
        try:
            with st.spinner("正在推进事件队列、分配资源并保存实验结果…"):
                outcome = execute_simulation(
                    database=database,
                    source=source,
                    preset=preset,
                    random_seed=int(random_seed),
                    wait_sla_seconds=int(wait_sla),
                    allow_skip_head=bool(allow_skip_head),
                    run_name=run_name,
                )
            st.session_state.selected_run_id = outcome.run_id
            st.toast(
                f"实验完成：{outcome.task_count} 个任务，结果哈希 {outcome.result.result_hash[:12]}",
                icon=":material/check_circle:",
            )
            st.rerun()
        except Exception as exc:
            st.error(str(exc), icon=":material/error:")

with database.session_scope() as session:
    recent = recent_runs(session, limit=20)

if not recent:
    st.info("尚无仿真实验。设置上方参数并运行实验后，将在此显示完整结果。", icon=":material/info:")
    st.stop()

run_labels = {
    row.id: f"{row.name} · {row.scheduler_preset} · {row.workload_label} · {row.started_at:%Y-%m-%d %H:%M}"
    for row in recent
}
selected_run_id = st.session_state.get("selected_run_id")
if selected_run_id not in run_labels:
    selected_run_id = recent[0].id
selected_run_id = st.selectbox(
    "查看历史实验",
    list(run_labels),
    index=list(run_labels).index(selected_run_id),
    format_func=lambda key: run_labels[key],
)
st.session_state.selected_run_id = selected_run_id

with database.session_scope() as session:
    run = session.get(type(recent[0]), selected_run_id)
    assert run is not None
    task_records = run_task_rows(session, selected_run_id)
    event_records = run_event_rows(session, selected_run_id)
    sample_records = run_sample_rows(session, selected_run_id)

metrics = run.metrics_json or {}
col1, col2, col3, col4 = st.columns(4)
with col1:
    label, unit, multiplier = METRIC_LABELS["average_wait_seconds"]
    st.metric(label, _metric_text(metrics.get("average_wait_seconds"), multiplier), unit, border=True)
with col2:
    label, unit, multiplier = METRIC_LABELS["makespan_seconds"]
    st.metric(label, _metric_text(metrics.get("makespan_seconds"), multiplier), unit, border=True)
with col3:
    label, unit, multiplier = METRIC_LABELS["gpu_utilization"]
    st.metric(label, _metric_text(metrics.get("gpu_utilization"), multiplier), unit, border=True)
with col4:
    label, unit, multiplier = METRIC_LABELS["completion_rate"]
    st.metric(label, _metric_text(metrics.get("completion_rate"), multiplier), unit, border=True)

with st.container(border=True):
    st.markdown(f"**{run.name}**")
    st.write(
        f"工作负载：{run.workload_label} · 预设：{run.scheduler_preset} · "
        f"任务 {run.task_count} 条 · 服务器 {run.server_count} 台"
    )
    st.caption(
        f"排序 {run.order_rule} / 放置 {run.placement_rule} · 种子 {run.random_seed} · "
        f"结果哈希 {run.result_hash[:24] if run.result_hash else '—'}"
    )

task_df = pd.DataFrame(
    [
        {
            "任务": row.task_name,
            "状态": row.status,
            "服务器": row.server_id or "—",
            "到达时间": row.submit_time,
            "开始时间": row.start_time,
            "结束时间": row.end_time,
            "等待时长": row.wait_time,
            "周转时长": row.turnaround_time,
            "GPU": row.gpu_required,
            "CPU": row.cpu_required,
            "内存 GB": row.memory_required_gb,
            "超时": "是" if row.timed_out else "否",
            "来源": row.source_type,
        }
        for row in task_records
    ]
)
sample_df = pd.DataFrame(
    [
        {
            "仿真时间": row.simulation_time,
            "GPU 分配": row.gpu_allocated,
            "CPU 分配": row.cpu_allocated,
            "内存分配": row.memory_allocated_gb,
            "GPU 利用率 %": row.gpu_allocated / row.gpu_capacity * 100 if row.gpu_capacity else 0,
            "CPU 利用率 %": row.cpu_allocated / row.cpu_capacity * 100 if row.cpu_capacity else 0,
            "内存利用率 %": row.memory_allocated_gb / row.memory_capacity_gb * 100 if row.memory_capacity_gb else 0,
        }
        for row in sample_records
    ]
)

section_header("动态资源时间线", "拖动仿真时间查看真实事件采样对应的资源状态。", icon=":material/timeline:")
if not sample_df.empty:
    max_time = float(sample_df["仿真时间"].max())
    selected_time = st.slider(
        "仿真时间 秒",
        min_value=0.0,
        max_value=max_time,
        value=0.0,
        step=max(max_time / 200.0, 1.0),
        key="simulation_time_slider",
    )
    up_to = sample_df[sample_df["仿真时间"] <= selected_time]
    snapshot = up_to.iloc[-1] if not up_to.empty else sample_df.iloc[0]
    active = task_df[
        task_df["开始时间"].notna()
        & task_df["结束时间"].notna()
        & (task_df["开始时间"] <= selected_time)
        & (task_df["结束时间"] > selected_time)
    ]
    dyn1, dyn2, dyn3, dyn4 = st.columns(4)
    with dyn1:
        st.metric("运行中任务", len(active), border=True)
    with dyn2:
        st.metric("GPU 已分配", f"{snapshot['GPU 分配']:.2f}", border=True)
    with dyn3:
        st.metric("CPU 已分配", f"{snapshot['CPU 分配']:.2f}", border=True)
    with dyn4:
        st.metric("内存已分配", f"{snapshot['内存分配']:.1f} GB", border=True)

    st.line_chart(
        sample_df,
        x="仿真时间",
        y=["GPU 利用率 %", "CPU 利用率 %", "内存利用率 %"],
        x_label="仿真时间（秒）",
        y_label="利用率（%）",
        alt="离散事件仿真产生的 GPU、CPU 和内存分配利用率时间线",
    )

section_header("任务执行甘特图", "条形直接来自引擎的开始、结束时间和服务器分配。", icon=":material/bar_chart:")
completed = task_df[task_df["开始时间"].notna() & task_df["结束时间"].notna()].copy()
if completed.empty:
    st.warning("本实验没有任务获得资源。", icon=":material/warning:")
else:
    completed["持续时间"] = completed["结束时间"] - completed["开始时间"]
    colors = ["#22D3EE", "#60A5FA", "#34D399", "#A78BFA", "#FBBF24", "#F87171", "#38BDF8"]
    figure = go.Figure()
    for index, (server_id, group) in enumerate(completed.groupby("服务器", sort=True)):
        figure.add_trace(
            go.Bar(
                x=group["持续时间"],
                y=group["任务"],
                base=group["开始时间"],
                orientation="h",
                name=str(server_id),
                marker_color=colors[index % len(colors)],
                customdata=group[["开始时间", "结束时间", "状态"]],
                hovertemplate=(
                    "任务：%{y}<br>开始：%{customdata[0]:,.0f}s"
                    "<br>结束：%{customdata[1]:,.0f}s<br>状态：%{customdata[2]}<extra></extra>"
                ),
            )
        )
    figure.update_layout(
        barmode="overlay",
        height=max(360, 32 * len(completed)),
        margin=dict(l=20, r=20, t=20, b=20),
        xaxis_title="仿真时间（秒）",
        yaxis_title="任务",
        legend_title="服务器",
    )
    st.plotly_chart(
        figure,
        width="stretch",
        config={"displayModeBar": False},
        alt="调度仿真任务执行甘特图，按服务器着色",
    )

section_header("评价指标", "指标由仿真事件和资源采样计算，公式版本 metrics-v1。", icon=":material/analytics:")
metric_rows = []
for key, (label, unit, multiplier) in METRIC_LABELS.items():
    value = metrics.get(key)
    metric_rows.append(
        {
            "指标": label,
            "数值": "—" if value is None else round(float(value) * multiplier, 4),
            "单位": unit,
        }
    )
st.dataframe(
    pd.DataFrame(metric_rows),
    hide_index=True,
    width="stretch",
    alt="当前仿真实验的评价指标",
)

with st.expander("任务结果与调度事件", icon=":material/list_alt:"):
    st.dataframe(
        task_df,
        hide_index=True,
        width="stretch",
        column_config={
            "到达时间": st.column_config.NumberColumn(format="%.0f"),
            "开始时间": st.column_config.NumberColumn(format="%.0f"),
            "结束时间": st.column_config.NumberColumn(format="%.0f"),
            "等待时长": st.column_config.NumberColumn(format="%.0f"),
            "周转时长": st.column_config.NumberColumn(format="%.0f"),
        },
        alt="当前仿真实验的逐任务执行结果",
    )
    events_df = pd.DataFrame(
        [
            {
                "序号": row.sequence_no,
                "仿真时间": row.event_time,
                "事件": row.event_type,
                "任务": row.task_id or "—",
                "服务器": row.server_id or "—",
                "说明": row.message,
            }
            for row in event_records
        ]
    )
    st.dataframe(
        events_df,
        hide_index=True,
        width="stretch",
        alt="当前仿真实验的调度事件日志",
    )

blocked = task_df[task_df["状态"] == "BLOCKED"]
if not blocked.empty:
    st.warning(
        f"本实验有 {len(blocked)} 个任务受阻。受阻任务没有获得服务器资源，可能来自资源不足、型号不匹配或严格队头阻塞。",
        icon=":material/warning:",
    )
