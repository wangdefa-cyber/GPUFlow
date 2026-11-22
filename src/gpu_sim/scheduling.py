"""Deterministic task ordering and server placement policies."""

from __future__ import annotations

from dataclasses import dataclass

from gpu_sim.domain import ResourceVector, ServerSpec, TaskSpec


@dataclass(frozen=True)
class PlacementChoice:
    server: ServerSpec | None
    score: float | None
    reason: str


def _task_sequence(task: TaskSpec) -> int:
    return task.sequence_no


def order_tasks(tasks: list[TaskSpec], rule: str) -> list[TaskSpec]:
    """Order waiting tasks deterministically for the selected rule."""
    normalized = rule.upper()
    if normalized == "SJF":
        return sorted(
            tasks,
            key=lambda task: (
                task.estimated_duration,
                task.submit_time,
                _task_sequence(task),
                task.id,
            ),
        )
    if normalized == "PRIORITY":
        return sorted(
            tasks,
            key=lambda task: (
                -task.priority,
                task.submit_time,
                _task_sequence(task),
                task.id,
            ),
        )
    return sorted(
        tasks,
        key=lambda task: (task.submit_time, _task_sequence(task), task.id),
    )


def task_fits_server(
    task: TaskSpec, server: ServerSpec, allocated: ResourceVector
) -> bool:
    """Check GPU type and all three resource dimensions."""
    if server.status != "Active":
        return False
    if task.gpu_type_required and task.gpu_type_required != server.gpu_type:
        return False
    remaining = server.capacity - allocated
    return task.demand.fits_within(remaining)


def _best_fit_score(
    task: TaskSpec,
    server: ServerSpec,
    allocated: ResourceVector,
    weights: tuple[float, float, float],
) -> float:
    remaining_after = server.capacity - allocated - task.demand
    dimensions = (
        (remaining_after.gpu, server.capacity.gpu),
        (remaining_after.cpu, server.capacity.cpu),
        (remaining_after.memory_gb, server.capacity.memory_gb),
    )
    score = 0.0
    for weight, (remaining, capacity) in zip(weights, dimensions, strict=True):
        ratio = remaining / capacity if capacity > 0 else 0.0
        score += weight * ratio
    return score


def choose_server(
    task: TaskSpec,
    servers: list[ServerSpec],
    allocations: dict[str, ResourceVector],
    placement_rule: str,
    weights: tuple[float, float, float] = (1.0, 1.0, 1.0),
) -> PlacementChoice:
    """Choose an eligible server using First Fit or multi-resource Best Fit."""
    candidates = [
        server
        for server in sorted(servers, key=lambda item: (item.name, item.id))
        if task_fits_server(task, server, allocations.get(server.id, ResourceVector()))
    ]
    if not candidates:
        return PlacementChoice(None, None, "no eligible server under current allocations")

    if placement_rule.upper() == "BEST_FIT":
        scored = [
            (
                _best_fit_score(
                    task, server, allocations.get(server.id, ResourceVector()), weights
                ),
                server,
            )
            for server in candidates
        ]
        score, server = min(scored, key=lambda item: (item[0], item[1].name, item[1].id))
        return PlacementChoice(server, score, "minimum weighted remaining-capacity ratio")

    server = candidates[0]
    return PlacementChoice(server, None, "first eligible server in stable order")
