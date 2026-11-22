"""Task-oriented persistence operations for the stage 4 application."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from gpu_sim.bootstrap import resource_from_record, seed_default_configuration
from gpu_sim.db import Database
from gpu_sim.domain import ResourceVector, SchedulerSpec, ServerSpec, SimulationResult, TaskSpec
from gpu_sim.models import (
    DatasetVersionRecord,
    GPUServerRecord,
    ResourceSampleRecord,
    RunMetricRecord,
    RunTaskResultRecord,
    SchedulerConfigRecord,
    SimulationEventRecord,
    SimulationRunRecord,
    SimulationTaskRecord,
)


METRIC_UNITS = {
    "average_wait_seconds": "秒",
    "average_turnaround_seconds": "秒",
    "makespan_seconds": "秒",
    "gpu_utilization": "%",
    "cpu_utilization": "%",
    "memory_utilization": "%",
    "completion_rate": "%",
    "timeout_rate": "%",
    "fairness_index": "0–1",
    "completed_tasks": "个",
    "blocked_tasks": "个",
}


def initialize_database(database: Database) -> None:
    with database.session_scope() as session:
        seed_default_configuration(session)


def list_servers(session: Session) -> list[GPUServerRecord]:
    return list(session.scalars(select(GPUServerRecord).order_by(GPUServerRecord.name)))


def server_dicts(session: Session) -> list[dict[str, Any]]:
    return [
        {
            "id": row.id,
            "name": row.name,
            "gpu_type": row.gpu_type,
            "gpu_capacity": row.gpu_capacity,
            "cpu_capacity": row.cpu_capacity,
            "memory_capacity_gb": row.memory_capacity_gb,
            "status": row.status,
        }
        for row in list_servers(session)
    ]


def replace_servers(session: Session, records: list[dict[str, Any]]) -> None:
    session.execute(delete(GPUServerRecord))
    for row in records:
        session.add(
            GPUServerRecord(
                id=str(row.get("id") or f"srv-{uuid4().hex[:8]}"),
                name=str(row["name"]).strip(),
                gpu_type=str(row["gpu_type"]).strip(),
                gpu_capacity=float(row["gpu_capacity"]),
                cpu_capacity=float(row["cpu_capacity"]),
                memory_capacity_gb=float(row["memory_capacity_gb"]),
                status=str(row["status"]).strip(),
            )
        )
    session.flush()


def user_task_dicts(session: Session) -> list[dict[str, Any]]:
    rows = session.scalars(
        select(SimulationTaskRecord)
        .where(SimulationTaskRecord.source_type == "USER_CREATED")
        .order_by(SimulationTaskRecord.sequence_no, SimulationTaskRecord.name)
    )
    return [
        {
            "id": row.id,
            "name": row.name,
            "source_type": row.source_type,
            "gpu_required": row.gpu_required,
            "cpu_required": row.cpu_required,
            "memory_required_gb": row.memory_required_gb,
            "priority": row.priority,
            "estimated_duration": row.estimated_duration,
            "gpu_type_required": row.gpu_type_required or "",
            "submit_time": row.submit_time,
        }
        for row in rows
    ]


def replace_user_tasks(session: Session, records: list[dict[str, Any]]) -> None:
    session.execute(
        delete(SimulationTaskRecord).where(
            SimulationTaskRecord.source_type == "USER_CREATED"
        )
    )
    for index, row in enumerate(records):
        session.add(
            SimulationTaskRecord(
                id=str(row.get("id") or f"task-{uuid4().hex[:8]}"),
                name=str(row["name"]).strip(),
                source_type="USER_CREATED",
                source_ref=None,
                user_key="LOCAL_USER",
                dataset_version_id=None,
                gpu_required=float(row["gpu_required"]),
                cpu_required=float(row["cpu_required"]),
                memory_required_gb=float(row["memory_required_gb"]),
                priority=int(row["priority"]),
                estimated_duration=float(row["estimated_duration"]),
                gpu_type_required=str(row.get("gpu_type_required") or "").strip() or None,
                submit_time=float(row["submit_time"]),
                sequence_no=index,
                is_active=True,
            )
        )
    session.flush()


def latest_historical_dataset(session: Session) -> DatasetVersionRecord | None:
    return session.scalar(
        select(DatasetVersionRecord)
        .order_by(DatasetVersionRecord.imported_at.desc())
        .limit(1)
    )


def task_dicts(
    session: Session, source: str
) -> tuple[list[dict[str, Any]], DatasetVersionRecord | None]:
    dataset = latest_historical_dataset(session) if source == "HISTORICAL_REPLAY" else None
    statement = select(SimulationTaskRecord).where(
        SimulationTaskRecord.source_type == source,
        SimulationTaskRecord.is_active.is_(True),
    )
    if dataset is not None:
        statement = statement.where(
            SimulationTaskRecord.dataset_version_id == dataset.id
        )
    rows = session.scalars(
        statement.order_by(
            SimulationTaskRecord.submit_time,
            SimulationTaskRecord.sequence_no,
            SimulationTaskRecord.name,
        )
    )
    return (
        [
            {
                "id": row.id,
                "name": row.name,
                "source_type": row.source_type,
                "source_ref": row.source_ref,
                "user_key": row.user_key,
                "gpu_required": row.gpu_required,
                "cpu_required": row.cpu_required,
                "memory_required_gb": row.memory_required_gb,
                "priority": row.priority,
                "estimated_duration": row.estimated_duration,
                "gpu_type_required": row.gpu_type_required or "",
                "submit_time": row.submit_time,
                "sequence_no": row.sequence_no,
            }
            for row in rows
        ],
        dataset,
    )


def scheduler_dicts(session: Session) -> list[dict[str, Any]]:
    rows = session.scalars(
        select(SchedulerConfigRecord).order_by(SchedulerConfigRecord.name)
    )
    return [
        {
            "id": row.id,
            "name": row.name,
            "preset": row.preset,
            "order_rule": row.order_rule,
            "placement_rule": row.placement_rule,
            "random_seed": row.random_seed,
            "wait_sla_seconds": row.wait_sla_seconds,
            "allow_skip_head": row.allow_skip_head,
            "weights": tuple(row.weights_json or [1.0, 1.0, 1.0]),
            "is_default": row.is_default,
        }
        for row in rows
    ]


def set_default_scheduler(
    session: Session,
    preset: str,
    random_seed: int,
    wait_sla_seconds: int,
    allow_skip_head: bool,
) -> None:
    rows = list(session.scalars(select(SchedulerConfigRecord)))
    target = next((row for row in rows if row.preset == preset), None)
    if target is None:
        raise ValueError(f"Unknown scheduler preset: {preset}")
    for row in rows:
        row.is_default = row.id == target.id
    target.random_seed = int(random_seed)
    target.wait_sla_seconds = int(wait_sla_seconds)
    target.allow_skip_head = bool(allow_skip_head)
    session.flush()


def to_server_specs(rows: list[GPUServerRecord]) -> list[ServerSpec]:
    return [
        ServerSpec(
            id=row.id,
            name=row.name,
            gpu_type=row.gpu_type,
            capacity=resource_from_record(row),
            status=row.status,
        )
        for row in rows
    ]


def to_task_specs(rows: list[dict[str, Any]]) -> list[TaskSpec]:
    return [
        TaskSpec(
            id=str(row["id"]),
            name=str(row["name"]),
            submit_time=float(row["submit_time"]),
            priority=int(row["priority"]),
            estimated_duration=float(row["estimated_duration"]),
            demand=ResourceVector(
                gpu=float(row["gpu_required"]),
                cpu=float(row["cpu_required"]),
                memory_gb=float(row["memory_required_gb"]),
            ),
            gpu_type_required=str(row.get("gpu_type_required") or "") or None,
            source_type=str(row.get("source_type") or "USER_CREATED"),
            source_ref=str(row.get("source_ref") or "") or None,
            user_key=str(row.get("user_key") or "UNKNOWN"),
            sequence_no=int(row.get("sequence_no", 0)),
        )
        for row in rows
    ]


def scheduler_spec(config: dict[str, Any]) -> SchedulerSpec:
    weights = tuple(float(value) for value in config.get("weights", (1.0, 1.0, 1.0)))
    return SchedulerSpec(
        preset=str(config["preset"]),
        order_rule=str(config["order_rule"]),
        placement_rule=str(config["placement_rule"]),
        random_seed=int(config["random_seed"]),
        wait_sla_seconds=int(config["wait_sla_seconds"]),
        allow_skip_head=bool(config.get("allow_skip_head", False)),
        weights=weights,
    )


def save_simulation_result(
    session: Session,
    result: SimulationResult,
    run_name: str,
    workload_label: str,
    task_snapshot: list[dict[str, Any]],
    server_snapshot: list[dict[str, Any]],
) -> str:
    run = SimulationRunRecord(
        id=result.run_id,
        name=run_name,
        workload_label=workload_label,
        scheduler_preset=result.config.preset,
        order_rule=result.config.order_rule,
        placement_rule=result.config.placement_rule,
        random_seed=result.config.random_seed,
        wait_sla_seconds=result.config.wait_sla_seconds,
        allow_skip_head=result.config.allow_skip_head,
        task_count=len(result.tasks),
        server_count=len(server_snapshot),
        status="COMPLETED",
        finished_at=datetime.now(timezone.utc),
        makespan_seconds=result.makespan,
        result_hash=result.result_hash,
        task_snapshot_json=task_snapshot,
        server_snapshot_json=server_snapshot,
        metrics_json=result.metrics,
    )
    session.add(run)
    session.flush()

    for event in result.events:
        session.add(
            SimulationEventRecord(
                run_id=run.id,
                sequence_no=event.sequence_no,
                event_time=event.event_time,
                event_type=event.event_type,
                task_id=event.task_id,
                server_id=event.server_id,
                message=event.message,
                payload_json=event.payload,
            )
        )

    for execution in result.tasks:
        row = execution.as_dict()
        session.add(
            RunTaskResultRecord(
                run_id=run.id,
                task_id=row["task_id"],
                task_name=row["task_name"],
                source_type=row["source_type"],
                source_ref=row["source_ref"],
                user_key=row["user_key"],
                status=row["status"],
                server_id=row["server_id"],
                submit_time=row["submit_time"],
                scheduled_time=row["scheduled_time"],
                start_time=row["start_time"],
                end_time=row["end_time"],
                wait_time=row["wait_time"],
                turnaround_time=row["turnaround_time"],
                estimated_duration=row["estimated_duration"],
                gpu_required=row["gpu_required"],
                cpu_required=row["cpu_required"],
                memory_required_gb=row["memory_required_gb"],
                gpu_type_required=row["gpu_type_required"] or None,
                timed_out=row["timed_out"],
            )
        )

    for name, value in result.metrics.items():
        session.add(
            RunMetricRecord(
                run_id=run.id,
                metric_name=name,
                metric_value=float(value) if value is not None else None,
                unit=METRIC_UNITS.get(name, ""),
            )
        )

    for sample in result.samples:
        session.add(
            ResourceSampleRecord(
                run_id=run.id,
                simulation_time=sample.simulation_time,
                gpu_allocated=sample.gpu_allocated,
                cpu_allocated=sample.cpu_allocated,
                memory_allocated_gb=sample.memory_allocated_gb,
                gpu_capacity=sample.gpu_capacity,
                cpu_capacity=sample.cpu_capacity,
                memory_capacity_gb=sample.memory_capacity_gb,
            )
        )
    session.flush()
    return run.id


def recent_runs(session: Session, limit: int = 10) -> list[SimulationRunRecord]:
    return list(
        session.scalars(
            select(SimulationRunRecord)
            .order_by(SimulationRunRecord.started_at.desc())
            .limit(limit)
        )
    )


def run_task_rows(session: Session, run_id: str) -> list[RunTaskResultRecord]:
    return list(
        session.scalars(
            select(RunTaskResultRecord)
            .where(RunTaskResultRecord.run_id == run_id)
            .order_by(RunTaskResultRecord.start_time, RunTaskResultRecord.task_name)
        )
    )


def run_event_rows(session: Session, run_id: str) -> list[SimulationEventRecord]:
    return list(
        session.scalars(
            select(SimulationEventRecord)
            .where(SimulationEventRecord.run_id == run_id)
            .order_by(SimulationEventRecord.sequence_no)
        )
    )


def run_sample_rows(session: Session, run_id: str) -> list[ResourceSampleRecord]:
    return list(
        session.scalars(
            select(ResourceSampleRecord)
            .where(ResourceSampleRecord.run_id == run_id)
            .order_by(ResourceSampleRecord.simulation_time)
        )
    )


def database_counts(session: Session) -> dict[str, int]:
    return {
        "servers": int(session.scalar(select(func.count()).select_from(GPUServerRecord)) or 0),
        "user_tasks": int(
            session.scalar(
                select(func.count())
                .select_from(SimulationTaskRecord)
                .where(SimulationTaskRecord.source_type == "USER_CREATED")
            )
            or 0
        ),
        "historical_tasks": int(
            session.scalar(
                select(func.count())
                .select_from(SimulationTaskRecord)
                .where(SimulationTaskRecord.source_type == "HISTORICAL_REPLAY")
            )
            or 0
        ),
        "runs": int(session.scalar(select(func.count()).select_from(SimulationRunRecord)) or 0),
    }


def reset_servers_to_defaults(session: Session) -> None:
    from gpu_sim.prototype.logic import DEFAULT_SERVERS

    session.execute(delete(GPUServerRecord))
    for row in DEFAULT_SERVERS:
        session.add(
            GPUServerRecord(
                id=row["id"],
                name=row["name"],
                gpu_type=row["gpu_type"],
                gpu_capacity=float(row["gpu_capacity"]),
                cpu_capacity=float(row["cpu_capacity"]),
                memory_capacity_gb=float(row["memory_capacity_gb"]),
                status=row["status"],
            )
        )
    session.flush()


def reset_user_tasks_to_defaults(session: Session) -> None:
    from gpu_sim.prototype.logic import DEFAULT_TASKS

    session.execute(
        delete(SimulationTaskRecord).where(
            SimulationTaskRecord.source_type == "USER_CREATED"
        )
    )
    for index, row in enumerate(DEFAULT_TASKS):
        session.add(
            SimulationTaskRecord(
                id=row["id"],
                name=row["name"],
                source_type="USER_CREATED",
                source_ref=None,
                user_key="LOCAL_USER",
                dataset_version_id=None,
                gpu_required=float(row["gpu_required"]),
                cpu_required=float(row["cpu_required"]),
                memory_required_gb=float(row["memory_required_gb"]),
                priority=int(row["priority"]),
                estimated_duration=float(row["estimated_duration"]),
                gpu_type_required=row["gpu_type_required"] or None,
                submit_time=float(row["submit_time"]),
                sequence_no=index,
                is_active=True,
            )
        )
    session.flush()
