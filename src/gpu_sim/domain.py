"""Core value objects and simulation result contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class ResourceVector:
    gpu: float = 0.0
    cpu: float = 0.0
    memory_gb: float = 0.0

    def __post_init__(self) -> None:
        if min(self.gpu, self.cpu, self.memory_gb) < 0:
            raise ValueError("Resource values cannot be negative")

    def fits_within(self, capacity: "ResourceVector") -> bool:
        return (
            self.gpu <= capacity.gpu
            and self.cpu <= capacity.cpu
            and self.memory_gb <= capacity.memory_gb
        )

    def __add__(self, other: "ResourceVector") -> "ResourceVector":
        return ResourceVector(
            self.gpu + other.gpu,
            self.cpu + other.cpu,
            self.memory_gb + other.memory_gb,
        )

    def __sub__(self, other: "ResourceVector") -> "ResourceVector":
        return ResourceVector(
            self.gpu - other.gpu,
            self.cpu - other.cpu,
            self.memory_gb - other.memory_gb,
        )

    def remaining_from(self, capacity: "ResourceVector") -> "ResourceVector":
        return capacity - self

    def as_dict(self) -> dict[str, float]:
        return asdict(self)


@dataclass(frozen=True)
class ServerSpec:
    id: str
    name: str
    gpu_type: str
    capacity: ResourceVector
    status: str = "Active"

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "gpu_type": self.gpu_type,
            "gpu_capacity": self.capacity.gpu,
            "cpu_capacity": self.capacity.cpu,
            "memory_capacity_gb": self.capacity.memory_gb,
            "status": self.status,
        }


@dataclass(frozen=True)
class TaskSpec:
    id: str
    name: str
    submit_time: float
    priority: int
    estimated_duration: float
    demand: ResourceVector
    gpu_type_required: str | None = None
    source_type: str = "USER_CREATED"
    source_ref: str | None = None
    user_key: str = "UNKNOWN"
    sequence_no: int = 0

    @property
    def duration(self) -> float:
        return self.estimated_duration

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "submit_time": self.submit_time,
            "priority": self.priority,
            "estimated_duration": self.estimated_duration,
            "gpu_required": self.demand.gpu,
            "cpu_required": self.demand.cpu,
            "memory_required_gb": self.demand.memory_gb,
            "gpu_type_required": self.gpu_type_required or "",
            "source_type": self.source_type,
            "source_ref": self.source_ref or "",
            "user_key": self.user_key,
            "sequence_no": self.sequence_no,
        }


@dataclass(frozen=True)
class SchedulerSpec:
    preset: str
    order_rule: str
    placement_rule: str
    random_seed: int
    wait_sla_seconds: int
    allow_skip_head: bool = False
    weights: tuple[float, float, float] = (1.0, 1.0, 1.0)

    def as_dict(self) -> dict[str, Any]:
        return {
            "preset": self.preset,
            "order_rule": self.order_rule,
            "placement_rule": self.placement_rule,
            "random_seed": self.random_seed,
            "wait_sla_seconds": self.wait_sla_seconds,
            "allow_skip_head": self.allow_skip_head,
            "weights": list(self.weights),
        }


@dataclass
class TaskExecution:
    task: TaskSpec
    status: str = "WAITING"
    server_id: str | None = None
    scheduled_time: float | None = None
    start_time: float | None = None
    end_time: float | None = None
    wait_time: float | None = None
    turnaround_time: float | None = None
    timed_out: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task.id,
            "task_name": self.task.name,
            "source_type": self.task.source_type,
            "source_ref": self.task.source_ref,
            "user_key": self.task.user_key,
            "status": self.status,
            "server_id": self.server_id,
            "submit_time": self.task.submit_time,
            "scheduled_time": self.scheduled_time,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "wait_time": self.wait_time,
            "turnaround_time": self.turnaround_time,
            "estimated_duration": self.task.estimated_duration,
            "gpu_required": self.task.demand.gpu,
            "cpu_required": self.task.demand.cpu,
            "memory_required_gb": self.task.demand.memory_gb,
            "gpu_type_required": self.task.gpu_type_required or "",
            "timed_out": self.timed_out,
        }


@dataclass(frozen=True)
class SimulationEvent:
    sequence_no: int
    event_time: float
    event_type: str
    task_id: str | None
    server_id: str | None
    message: str
    payload: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ResourceSample:
    simulation_time: float
    gpu_allocated: float
    cpu_allocated: float
    memory_allocated_gb: float
    gpu_capacity: float
    cpu_capacity: float
    memory_capacity_gb: float

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SimulationResult:
    run_id: str
    tasks: list[TaskExecution]
    events: list[SimulationEvent]
    samples: list[ResourceSample]
    metrics: dict[str, float | None]
    makespan: float | None
    result_hash: str
    config: SchedulerSpec

    def task_rows(self) -> list[dict[str, Any]]:
        return [task.as_dict() for task in self.tasks]

    def event_rows(self) -> list[dict[str, Any]]:
        return [event.as_dict() for event in self.events]

    def sample_rows(self) -> list[dict[str, Any]]:
        return [sample.as_dict() for sample in self.samples]
