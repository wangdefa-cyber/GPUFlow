"""Read-only access to real Alibaba trace summaries for the prototype."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[3]
REPORTS_DIR = PROJECT_ROOT / "reports"
DATA_DIR = PROJECT_ROOT / "data"

JOB_COLUMNS = ["job_name", "inst_id", "user", "status", "start_time", "end_time"]
TASK_COLUMNS = [
    "job_name",
    "task_name",
    "inst_num",
    "status",
    "start_time",
    "end_time",
    "plan_cpu",
    "plan_mem",
    "plan_gpu",
    "gpu_type",
]
MACHINE_COLUMNS = ["machine", "gpu_type", "cap_cpu", "cap_mem", "cap_gpu"]


@st.cache_data(show_spinner=False)
def load_audit_payload() -> dict[str, Any]:
    """Load the machine-readable audit generated from the real CSV files."""
    path = REPORTS_DIR / "data_audit.json"
    return json.loads(path.read_text(encoding="utf-8"))


@st.cache_data(show_spinner=False)
def table_profiles() -> pd.DataFrame:
    """Return a compact table-level profile for the data center."""
    rows = []
    for table in load_audit_payload()["tables"]:
        rows.append(
            {
                "数据表": table["table"],
                "行数": table["rows"],
                "字段数": table["columns"],
                "文件大小 MB": table["file_size_mb"],
                "缺失单元格": sum(field["missing"] for field in table["fields"]),
                "重复行": table["duplicate_rows_by_full_row_hash"],
                "校验和": "通过" if table["checksum_match"] else "失败",
            }
        )
    return pd.DataFrame(rows)


@st.cache_data(show_spinner=False)
def categorical_distribution(table_name: str, column: str) -> pd.DataFrame:
    """Return a real categorical distribution recorded by the audit."""
    payload = load_audit_payload()
    table = next(item for item in payload["tables"] if item["table"] == table_name)
    values = table["categorical_profile"][column]
    rows = []
    for label, count in values.items():
        display_label = "未提供" if label == "<NULL>" else label
        rows.append({"分类": display_label, "数量": count})
    return pd.DataFrame(rows)


@st.cache_data(show_spinner=False)
def dataset_summary() -> dict[str, Any]:
    """Aggregate real trace scale and GPU capacity metrics."""
    payload = load_audit_payload()
    tables = {table["table"]: table for table in payload["tables"]}
    machine_spec = machine_specs()
    job_status = tables["pai_job_table"]["categorical_profile"]["status"]
    return {
        "total_rows": sum(table["rows"] for table in payload["tables"]),
        "job_rows": tables["pai_job_table"]["rows"],
        "instance_rows": tables["pai_instance_table"]["rows"],
        "sensor_rows": tables["pai_sensor_table"]["rows"],
        "machine_count": tables["pai_machine_spec"]["rows"],
        "total_gpu": float(machine_spec["cap_gpu"].sum()),
        "terminated_jobs": int(job_status.get("Terminated", 0)),
        "failed_jobs": int(job_status.get("Failed", 0)),
        "running_jobs": int(job_status.get("Running", 0)),
        "waiting_jobs": int(job_status.get("Waiting", 0)),
    }


@st.cache_data(show_spinner=False)
def machine_specs() -> pd.DataFrame:
    """Load the complete, small real machine specification table."""
    path = DATA_DIR / "pai_machine_spec" / "pai_machine_spec.csv"
    return pd.read_csv(
        path,
        header=None,
        names=MACHINE_COLUMNS,
        dtype={"machine": "string", "gpu_type": "string"},
    )


@st.cache_data(show_spinner=False)
def gpu_capacity_by_type() -> pd.DataFrame:
    """Aggregate real machine counts and GPU capacity by GPU type."""
    specs = machine_specs()
    grouped = (
        specs.groupby("gpu_type", as_index=False)
        .agg(
            机器数=("machine", "size"),
            GPU总量=("cap_gpu", "sum"),
            平均CPU核数=("cap_cpu", "mean"),
            平均内存GB=("cap_mem", "mean"),
        )
        .sort_values("GPU总量", ascending=False)
    )
    return grouped


@st.cache_data(show_spinner=False)
def historical_job_preview(limit: int = 300) -> pd.DataFrame:
    """Load a bounded real job sample; this is a preview, not a full query."""
    path = DATA_DIR / "pai_job_table" / "pai_job_table.csv"
    return pd.read_csv(
        path,
        header=None,
        names=JOB_COLUMNS,
        nrows=limit,
        dtype={"job_name": "string", "inst_id": "string", "user": "string", "status": "string"},
    )


@st.cache_data(show_spinner=False)
def historical_task_preview(limit: int = 300) -> pd.DataFrame:
    """Load a bounded real task sample; this is a preview, not a full query."""
    path = DATA_DIR / "pai_task_table" / "pai_task_table.csv"
    return pd.read_csv(
        path,
        header=None,
        names=TASK_COLUMNS,
        nrows=limit,
        dtype={"job_name": "string", "task_name": "string", "status": "string", "gpu_type": "string"},
    )


@st.cache_data(show_spinner=False)
def quality_flags() -> pd.DataFrame:
    """Expose the most important limitations found by the stage 1 audit."""
    return pd.DataFrame(
        [
            {
                "质量主题": "状态性缺失",
                "结论": "失败、等待、运行中和中断记录存在结构性空时间",
                "影响": "不能直接 dropna，也不能把空结束时间当作 0 时长",
            },
            {
                "质量主题": "观测覆盖",
                "结论": "sensor 覆盖约 42.14%，machine_metric 覆盖约 28.05% 的实例",
                "影响": "历史利用率不代表全集群完整观测",
            },
            {
                "质量主题": "GPU 指标口径",
                "结论": "machine_gpu 原始值可超过 100，需按机器 GPU 容量解释",
                "影响": "不能直接当作单卡 0–100% 使用率",
            },
            {
                "质量主题": "时间语义",
                "结论": "start_time/end_time 是脱敏相对秒数",
                "影响": "界面不得显示为真实历史日历日期",
            },
            {
                "质量主题": "语义标签",
                "结论": "workload 缺失 90.26%，gpu_type_spec 缺失 98.04%",
                "影响": "只能作为可选分析标签",
            },
        ]
    )
