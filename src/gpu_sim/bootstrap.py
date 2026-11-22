"""Initial configuration copied into SQLite once."""

from __future__ import annotations

from sqlalchemy.orm import Session

from gpu_sim.domain import ResourceVector
from gpu_sim.models import AppSettingRecord, GPUServerRecord, SchedulerConfigRecord, SimulationTaskRecord
from gpu_sim.prototype.logic import DEFAULT_SERVERS, DEFAULT_TASKS, PRESETS


SEED_SETTING_KEY = "stage4_seed_v1"


def seed_default_configuration(session: Session) -> None:
    """Seed mutable system configuration once, never from historical CSV."""
    if session.get(AppSettingRecord, SEED_SETTING_KEY):
        return

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

    for index, (key, config) in enumerate(PRESETS.items()):
        session.add(
            SchedulerConfigRecord(
                id=f"sched-{index + 1}",
                name=key,
                preset=key,
                order_rule=config["order_rule"],
                placement_rule=config["placement_rule"],
                random_seed=20261122,
                wait_sla_seconds=900,
                allow_skip_head=False,
                weights_json=[1.0, 1.0, 1.0],
                is_default=index == 0,
            )
        )

    session.add(AppSettingRecord(key=SEED_SETTING_KEY, value="seeded"))
    session.flush()


def resource_from_record(row: GPUServerRecord) -> ResourceVector:
    return ResourceVector(
        gpu=float(row.gpu_capacity),
        cpu=float(row.cpu_capacity),
        memory_gb=float(row.memory_capacity_gb),
    )
