from __future__ import annotations

import streamlit as st

from gpu_sim.db import get_database
from gpu_sim.importer import import_historical_workload_sample
from gpu_sim.prototype import data_access
from gpu_sim.prototype.ui import page_caption, source_badge
from gpu_sim.services import database_counts, latest_historical_dataset


page_caption(
    "数据中心展示真实 CSV 的审计结果、有限行数预览，以及阶段 4 的 SQLite 历史工作负载导入。"
)
source_badge("HISTORICAL")

tabs = st.tabs(["数据概况", "质量检查", "真实样例", "数据库导入"])

with tabs[0]:
    profiles = data_access.table_profiles()
    st.dataframe(
        profiles,
        hide_index=True,
        width="stretch",
        column_config={
            "行数": st.column_config.NumberColumn(format="localized"),
            "字段数": st.column_config.NumberColumn(format="%d"),
            "文件大小 MB": st.column_config.NumberColumn(format="%.3f"),
            "缺失单元格": st.column_config.NumberColumn(format="localized"),
            "重复行": st.column_config.NumberColumn(format="localized"),
        },
        alt="七张阿里巴巴 GPU Trace 数据表的行数、字段数、大小、缺失、重复和校验结果",
    )
    st.caption("所有表的 SHA-256 均与官方 README 公布值一致。")

    left, right = st.columns(2)
    with left:
        with st.container(border=True):
            st.markdown("**作业状态**")
            jobs = data_access.categorical_distribution("pai_job_table", "status")
            st.bar_chart(
                jobs,
                x="分类",
                y="数量",
                x_label="状态",
                y_label="作业数",
                alt="真实历史作业状态数量",
            )
    with right:
        with st.container(border=True):
            st.markdown("**任务状态**")
            tasks = data_access.categorical_distribution("pai_task_table", "status")
            st.bar_chart(
                tasks,
                x="分类",
                y="数量",
                x_label="状态",
                y_label="任务数",
                alt="真实历史任务状态数量",
            )

with tabs[1]:
    st.markdown("**关键质量结论**")
    st.dataframe(
        data_access.quality_flags(),
        hide_index=True,
        width="stretch",
        alt="真实 GPU Trace 的状态缺失、观测覆盖、GPU 指标口径、时间语义和标签覆盖问题",
    )
    st.warning(
        "缺失值与状态强相关。后续导入不会直接删除空值记录，也不会把历史监控指标当作未来仿真结果。",
        icon=":material/warning:",
    )

with tabs[2]:
    col1, col2 = st.columns([1, 3])
    with col1:
        limit = st.selectbox("预览行数", [100, 300, 1000], index=1, key="data_preview_limit")
    jobs = data_access.historical_job_preview(limit)
    tasks = data_access.historical_task_preview(limit)

    preview_kind = st.radio("选择真实样例", ["作业", "任务"], horizontal=True, key="data_preview_kind")
    if preview_kind == "作业":
        statuses = ["全部", *sorted(jobs["status"].dropna().unique().tolist())]
        status_filter = st.selectbox("作业状态筛选", statuses, key="job_preview_status")
        shown = jobs if status_filter == "全部" else jobs[jobs["status"] == status_filter]
        st.dataframe(shown, hide_index=True, width="stretch", alt="真实历史作业 CSV 前若干行预览")
    else:
        statuses = ["全部", *sorted(tasks["status"].dropna().unique().tolist())]
        status_filter = st.selectbox("任务状态筛选", statuses, key="task_preview_status")
        shown = tasks if status_filter == "全部" else tasks[tasks["status"] == status_filter]
        st.dataframe(shown, hide_index=True, width="stretch", alt="真实历史任务 CSV 前若干行预览")

    st.caption("以上为真实 CSV 的有限行数预览，不是全量分页查询；时间字段为脱敏相对秒数。")
with tabs[3]:
    database = get_database()
    with database.session_scope() as session:
        counts = database_counts(session)
        latest = latest_historical_dataset(session)
        latest_label = latest.version_code if latest else "尚未导入"

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("SQLite 用户任务", counts["user_tasks"], border=True)
    with col2:
        st.metric("历史回放任务", counts["historical_tasks"], border=True)
    with col3:
        st.metric("仿真实验", counts["runs"], border=True)

    st.caption(f"数据库：{database.path} · 最新历史样本：{latest_label}")
    st.write(
        "导入会从真实 instance 表中读取前若干条已终止且时长大于 0 的实例，"
        "按 job_name + task_name 关联 task 资源计划，并转换为单机仿真任务。"
    )
    st.warning(
        "这是有界历史样本，不是全量实例回放。历史 task 没有优先级，样本统一使用中性优先级 5，并在数据集元数据中记录该假设。",
        icon=":material/info:",
    )
    task_limit = st.select_slider(
        "历史样本任务数量",
        options=[20, 50, 80, 120, 200],
        value=80,
        key="history_import_limit",
    )
    if st.button("导入真实历史工作负载样本", icon=":material/cloud_download:", width="stretch"):
        with st.status("导入真实历史工作负载样本", expanded=True) as status:
            try:
                dataset_id, task_count = import_historical_workload_sample(
                    database,
                    task_limit=task_limit,
                    progress=lambda message: status.write(message),
                )
                status.update(
                    label=f"导入完成：{task_count} 个历史任务",
                    state="complete",
                    expanded=False,
                )
                st.success(f"数据集 {dataset_id} 已写入 SQLite。", icon=":material/check_circle:")
            except Exception as exc:
                status.update(label="导入失败", state="error", expanded=True)
                st.error(str(exc), icon=":material/error:")
