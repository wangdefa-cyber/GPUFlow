"""Import a bounded, real historical workload sample from the Alibaba trace."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Callable

import pandas as pd
from sqlalchemy import select

from gpu_sim.db import Database
from gpu_sim.models import DatasetVersionRecord, SimulationTaskRecord


PROJECT_ROOT = Path(__file__).resolve().parents[2]
INSTANCE_PATH = PROJECT_ROOT / "data" / "pai_instance_table" / "pai_instance_table.csv"
TASK_PATH = PROJECT_ROOT / "data" / "pai_task_table" / "pai_task_table.csv"
JOB_PATH = PROJECT_ROOT / "data" / "pai_job_table" / "pai_job_table.csv"

INSTANCE_COLUMNS = [
    "job_name", "task_name", "inst_name", "worker_name", "inst_id",
    "status", "start_time", "end_time", "machine",
]
TASK_COLUMNS = [
    "job_name", "task_name", "inst_num", "status", "start_time", "end_time",
    "plan_cpu", "plan_mem", "plan_gpu", "gpu_type",
]
JOB_COLUMNS = ["job_name", "inst_id", "user", "status", "start_time", "end_time"]


def _sample_key(limit: int) -> str:
    instance_stat = INSTANCE_PATH.stat()
    task_stat = TASK_PATH.stat()
    raw = f"{limit}|{instance_stat.st_size}|{task_stat.st_size}|{task_stat.st_mtime_ns}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def import_historical_workload_sample(
    database: Database,
    task_limit: int = 80,
    progress: Callable[[str], None] | None = None,
) -> tuple[str, int]:
    """Map real terminated instances to single-server simulation tasks."""
    limit = max(1, min(int(task_limit), 500))
    version_code = f"history-sample-{limit}-{_sample_key(limit)}"
    notify = progress or (lambda _message: None)

    with database.session_scope() as session:
        existing = session.scalar(
            select(DatasetVersionRecord).where(
                DatasetVersionRecord.version_code == version_code
            )
        )
        if existing is not None:
            return existing.id, existing.task_count

    notify("读取真实历史实例样本…")
    instance_preview = pd.read_csv(
        INSTANCE_PATH,
        header=None,
        names=INSTANCE_COLUMNS,
        nrows=max(limit * 30, 2_000),
        dtype={
            "job_name": "string", "task_name": "string", "inst_name": "string",
            "worker_name": "string", "inst_id": "string", "status": "string",
            "machine": "string",
        },
    )
    candidates = instance_preview[
        instance_preview["status"].eq("Terminated")
        & instance_preview["worker_name"].notna()
        & instance_preview["machine"].notna()
        & instance_preview["start_time"].notna()
        & instance_preview["end_time"].notna()
    ].copy()
    candidates["duration"] = candidates["end_time"] - candidates["start_time"]
    candidates = candidates[candidates["duration"] > 0].copy()
    if candidates.empty:
        raise ValueError("No terminated, positive-duration instance records were found")
    candidate_pairs = set(zip(candidates["job_name"], candidates["task_name"], strict=True))
    candidate_jobs = set(candidates["job_name"])

    notify("扫描真实历史任务表并匹配资源计划…")
    task_rows: list[dict[str, object]] = []
    for chunk in pd.read_csv(
        TASK_PATH,
        header=None,
        names=TASK_COLUMNS,
        chunksize=200_000,
        dtype={"job_name": "string", "task_name": "string", "status": "string", "gpu_type": "string"},
    ):
        pairs = list(zip(chunk["job_name"], chunk["task_name"], strict=True))
        mask = pd.Series([pair in candidate_pairs for pair in pairs], index=chunk.index, dtype=bool)
        selected = chunk[
            mask
            & chunk["status"].eq("Terminated")
            & chunk["plan_cpu"].notna()
            & chunk["plan_mem"].notna()
            & chunk["plan_gpu"].notna()
        ]
        if not selected.empty:
            task_rows.extend(selected.to_dict("records"))
    if not task_rows:
        raise ValueError("No matching historical task resource plans were found")

    notify("扫描真实历史作业表并补充用户维度…")
    users: dict[str, str] = {}
    for chunk in pd.read_csv(
        JOB_PATH,
        header=None,
        names=JOB_COLUMNS,
        chunksize=200_000,
        dtype={"job_name": "string", "inst_id": "string", "user": "string", "status": "string"},
    ):
        selected = chunk[chunk["job_name"].isin(candidate_jobs)]
        for job_name, user in zip(selected["job_name"], selected["user"], strict=True):
            users[str(job_name)] = str(user) if pd.notna(user) else "UNKNOWN"

    task_lookup = {(str(row["job_name"]), str(row["task_name"])): row for row in task_rows}
    matched: list[dict[str, object]] = []
    for row in candidates.to_dict("records"):
        key = (str(row["job_name"]), str(row["task_name"]))
        plan = task_lookup.get(key)
        if plan is None:
            continue
        matched.append(
            {
                **row,
                "plan_cpu": plan["plan_cpu"],
                "plan_mem": plan["plan_mem"],
                "plan_gpu": plan["plan_gpu"],
                "gpu_type": plan.get("gpu_type"),
            }
        )
        if len(matched) >= limit:
            break
    if not matched:
        raise ValueError("No instance could be joined to a valid task resource plan")

    min_start = min(float(row["start_time"]) for row in matched)
    dataset_id = f"dataset-{version_code}"
    task_records: list[SimulationTaskRecord] = []
    for index, row in enumerate(matched):
        worker_name = str(row["worker_name"])
        task_id = "hist-" + hashlib.sha1(
            f"{version_code}|{worker_name}".encode("utf-8")
        ).hexdigest()[:16]
        task_records.append(
            SimulationTaskRecord(
                id=task_id,
                name=(
                    f"{str(row['job_name'])[:8]} / {row['task_name']} / "
                    f"{str(row['inst_name'])[:8]}"
                ),
                source_type="HISTORICAL_REPLAY",
                source_ref=worker_name,
                user_key=users.get(str(row["job_name"]), "UNKNOWN"),
                dataset_version_id=dataset_id,
                gpu_required=float(row["plan_gpu"]) / 100.0,
                cpu_required=float(row["plan_cpu"]) / 100.0,
                memory_required_gb=float(row["plan_mem"]),
                priority=5,
                estimated_duration=float(row["duration"]),
                gpu_type_required=str(row.get("gpu_type") or "") or None,
                submit_time=max(0.0, float(row["start_time"]) - min_start),
                sequence_no=index,
                is_active=True,
            )
        )

    notify("写入 SQLite 历史工作负载样本…")
    with database.session_scope() as session:
        existing = session.get(DatasetVersionRecord, dataset_id)
        if existing is not None:
            return existing.id, existing.task_count
        machine_count = len({str(row["machine"]) for row in matched})
        session.add(
            DatasetVersionRecord(
                id=dataset_id,
                version_code=version_code,
                source_uri=(
                    "https://github.com/alibaba/clusterdata/tree/master/"
                    "cluster-trace-gpu-v2020"
                ),
                task_count=len(task_records),
                machine_count=machine_count,
                metadata_json={
                    "sample_mode": "FIRST_TERMINATED_INSTANCES",
                    "task_limit": limit,
                    "source_files": [str(INSTANCE_PATH), str(TASK_PATH), str(JOB_PATH)],
                    "priority_source": "DEFAULT_5_HISTORICAL_RECORD_HAS_NO_PRIORITY",
                    "duration_source": "instance_end_time - instance_start_time",
                    "resource_source": "pai_task_table plan units converted to equivalents",
                },
            )
        )
        session.add_all(task_records)
        session.flush()
        return dataset_id, len(task_records)
