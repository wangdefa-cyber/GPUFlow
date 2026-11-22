from __future__ import annotations

from gpu_sim.domain import ResourceVector, SchedulerSpec, ServerSpec, TaskSpec
from gpu_sim.simulation import EngineInput, SimulationEngine


def task(task_id: str, *, submit: float, duration: float, user: str) -> TaskSpec:
    return TaskSpec(
        id=task_id,
        name=task_id,
        submit_time=submit,
        priority=5,
        estimated_duration=duration,
        demand=ResourceVector(gpu=1, cpu=1, memory_gb=1),
        user_key=user,
    )


def scheduler(*, wait_sla: int) -> SchedulerSpec:
    return SchedulerSpec(
        preset="FIFO",
        order_rule="FIFO",
        placement_rule="FIRST_FIT",
        random_seed=7,
        wait_sla_seconds=wait_sla,
        allow_skip_head=False,
    )


def test_timeout_and_fairness_metrics() -> None:
    server = ServerSpec(
        id="s1",
        name="A",
        gpu_type="V100",
        capacity=ResourceVector(gpu=1, cpu=4, memory_gb=16),
    )
    result = SimulationEngine(
        EngineInput(
            run_id="metrics",
            tasks=[
                task("t1", submit=0, duration=10, user="a"),
                task("t2", submit=0, duration=10, user="b"),
            ],
            servers=[server],
            scheduler=scheduler(wait_sla=5),
        )
    ).run()

    assert result.metrics["timeout_rate"] == 0.5
    assert result.metrics["fairness_index"] == 1.0
    assert result.metrics["completion_rate"] == 1.0


def test_resource_samples_never_exceed_capacity() -> None:
    server = ServerSpec(
        id="s1",
        name="A",
        gpu_type="V100",
        capacity=ResourceVector(gpu=2, cpu=8, memory_gb=32),
    )
    tasks = [
        TaskSpec(
            id=f"t{index}",
            name=f"t{index}",
            submit_time=float(index),
            priority=5,
            estimated_duration=10,
            demand=ResourceVector(gpu=1, cpu=2, memory_gb=4),
        )
        for index in range(4)
    ]
    result = SimulationEngine(
        EngineInput(
            run_id="samples",
            tasks=tasks,
            servers=[server],
            scheduler=scheduler(wait_sla=900),
        )
    ).run()

    for sample in result.samples:
        assert sample.gpu_allocated <= sample.gpu_capacity
        assert sample.cpu_allocated <= sample.cpu_capacity
        assert sample.memory_allocated_gb <= sample.memory_capacity_gb
