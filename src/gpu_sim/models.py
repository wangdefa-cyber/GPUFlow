"""SQLAlchemy persistence models for the stage 4 closed loop."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class DatasetVersionRecord(Base):
    __tablename__ = "dataset_version"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    version_code: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    source_uri: Mapped[str] = mapped_column(Text, nullable=False)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    task_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    machine_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class GPUServerRecord(Base):
    __tablename__ = "gpu_server"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    gpu_type: Mapped[str] = mapped_column(String(32), nullable=False)
    gpu_capacity: Mapped[float] = mapped_column(Float, nullable=False)
    cpu_capacity: Mapped[float] = mapped_column(Float, nullable=False)
    memory_capacity_gb: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="Active", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class SimulationTaskRecord(Base):
    __tablename__ = "simulation_task"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_ref: Mapped[str | None] = mapped_column(String(512), nullable=True)
    user_key: Mapped[str] = mapped_column(String(128), default="UNKNOWN", nullable=False)
    dataset_version_id: Mapped[str | None] = mapped_column(ForeignKey("dataset_version.id"), nullable=True)
    gpu_required: Mapped[float] = mapped_column(Float, nullable=False)
    cpu_required: Mapped[float] = mapped_column(Float, nullable=False)
    memory_required_gb: Mapped[float] = mapped_column(Float, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    estimated_duration: Mapped[float] = mapped_column(Float, nullable=False)
    gpu_type_required: Mapped[str | None] = mapped_column(String(32), nullable=True)
    submit_time: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    sequence_no: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class SchedulerConfigRecord(Base):
    __tablename__ = "scheduler_config"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    preset: Mapped[str] = mapped_column(String(32), nullable=False)
    order_rule: Mapped[str] = mapped_column(String(32), nullable=False)
    placement_rule: Mapped[str] = mapped_column(String(32), nullable=False)
    random_seed: Mapped[int] = mapped_column(Integer, default=20261122, nullable=False)
    wait_sla_seconds: Mapped[int] = mapped_column(Integer, default=900, nullable=False)
    allow_skip_head: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    weights_json: Mapped[list[float]] = mapped_column(JSON, default=list, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class SimulationRunRecord(Base):
    __tablename__ = "simulation_run"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    workload_label: Mapped[str] = mapped_column(String(256), nullable=False)
    scheduler_preset: Mapped[str] = mapped_column(String(32), nullable=False)
    order_rule: Mapped[str] = mapped_column(String(32), nullable=False)
    placement_rule: Mapped[str] = mapped_column(String(32), nullable=False)
    random_seed: Mapped[int] = mapped_column(Integer, nullable=False)
    wait_sla_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    allow_skip_head: Mapped[bool] = mapped_column(Boolean, nullable=False)
    task_count: Mapped[int] = mapped_column(Integer, nullable=False)
    server_count: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    makespan_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    result_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    task_snapshot_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    server_snapshot_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    metrics_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class SimulationEventRecord(Base):
    __tablename__ = "simulation_event"
    __table_args__ = (UniqueConstraint("run_id", "sequence_no", name="uq_event_run_sequence"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("simulation_run.id"), nullable=False, index=True)
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    event_time: Mapped[float] = mapped_column(Float, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    task_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    server_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class RunTaskResultRecord(Base):
    __tablename__ = "run_task_result"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("simulation_run.id"), nullable=False, index=True)
    task_id: Mapped[str] = mapped_column(String(64), nullable=False)
    task_name: Mapped[str] = mapped_column(String(256), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_ref: Mapped[str | None] = mapped_column(String(512), nullable=True)
    user_key: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    server_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    submit_time: Mapped[float] = mapped_column(Float, nullable=False)
    scheduled_time: Mapped[float | None] = mapped_column(Float, nullable=True)
    start_time: Mapped[float | None] = mapped_column(Float, nullable=True)
    end_time: Mapped[float | None] = mapped_column(Float, nullable=True)
    wait_time: Mapped[float | None] = mapped_column(Float, nullable=True)
    turnaround_time: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimated_duration: Mapped[float] = mapped_column(Float, nullable=False)
    gpu_required: Mapped[float] = mapped_column(Float, nullable=False)
    cpu_required: Mapped[float] = mapped_column(Float, nullable=False)
    memory_required_gb: Mapped[float] = mapped_column(Float, nullable=False)
    gpu_type_required: Mapped[str | None] = mapped_column(String(32), nullable=True)
    timed_out: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class RunMetricRecord(Base):
    __tablename__ = "run_metric"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("simulation_run.id"), nullable=False, index=True)
    metric_name: Mapped[str] = mapped_column(String(128), nullable=False)
    metric_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    formula_version: Mapped[str] = mapped_column(String(32), default="metrics-v1", nullable=False)


class ResourceSampleRecord(Base):
    __tablename__ = "resource_sample"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("simulation_run.id"), nullable=False, index=True)
    simulation_time: Mapped[float] = mapped_column(Float, nullable=False)
    gpu_allocated: Mapped[float] = mapped_column(Float, nullable=False)
    cpu_allocated: Mapped[float] = mapped_column(Float, nullable=False)
    memory_allocated_gb: Mapped[float] = mapped_column(Float, nullable=False)
    gpu_capacity: Mapped[float] = mapped_column(Float, nullable=False)
    cpu_capacity: Mapped[float] = mapped_column(Float, nullable=False)
    memory_capacity_gb: Mapped[float] = mapped_column(Float, nullable=False)


class AppSettingRecord(Base):
    __tablename__ = "app_setting"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
