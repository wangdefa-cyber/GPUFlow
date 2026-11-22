from __future__ import annotations

from gpu_sim.domain import ResourceVector, SchedulerSpec, ServerSpec, TaskSpec
from gpu_sim.scheduling import choose_server
from gpu_sim.simulation import EngineInput, SimulationEngine


def task(task_id: str, *, submit: float = 0, duration: float = 10, gpu: float = 1, cpu: float = 1, memory: float = 1, priority: int = 5) -> TaskSpec:
    return TaskSpec(
        id=task_id,
        name=task_id,
        submit_time=submit,
        priority=priority,
        estimated_duration=duration,
        demand=ResourceVector(gpu=gpu, cpu=cpu, memory_gb=memory),
        user_key="user-a",
    )


def server(server_id: str, name: str, gpu: float = 1) -> ServerSpec:
    return ServerSpec(
        id=server_id,
        name=name,
        gpu_type="V100",
        capacity=ResourceVector(gpu=gpu, cpu=16, memory_gb=128),
    )


def scheduler(rule: str = "FIFO", placement: str = "FIRST_FIT", skip: bool = False) -> SchedulerSpec:
    return SchedulerSpec(
        preset=rule,
        order_rule=rule,
        placement_rule=placement,
        random_seed=42,
        wait_sla_seconds=4,
        allow_skip_head=skip,
    )


def test_fifo_schedules_in_arrival_order_and_releases_resources() -> None:
    engine = SimulationEngine(
        EngineInput(
            run_id="run-1",
            tasks=[task("t1", duration=10), task("t2", duration=5)],
            servers=[server("s1", "A")],
            scheduler=scheduler(),
        )
    )
    result = engine.run()

    by_id = {execution.task.id: execution for execution in result.tasks}
    assert by_id["t1"].start_time == 0
    assert by_id["t1"].end_time == 10
    assert by_id["t2"].start_time == 10
    assert by_id["t2"].end_time == 15
    assert result.metrics["completion_rate"] == 1.0
    assert result.metrics["average_wait_seconds"] == 5.0
    assert result.makespan == 15


def test_sjf_places_shortest_task_first() -> None:
    engine = SimulationEngine(
        EngineInput(
            run_id="run-sjf",
            tasks=[task("long", duration=10), task("short", duration=2)],
            servers=[server("s1", "A")],
            scheduler=scheduler("SJF"),
        )
    )
    result = engine.run()
    by_id = {execution.task.id: execution for execution in result.tasks}
    assert by_id["short"].start_time == 0
    assert by_id["long"].start_time == 2


def test_priority_places_highest_priority_first() -> None:
    engine = SimulationEngine(
        EngineInput(
            run_id="run-priority",
            tasks=[task("low", priority=1), task("high", priority=9)],
            servers=[server("s1", "A")],
            scheduler=scheduler("PRIORITY"),
        )
    )
    result = engine.run()
    by_id = {execution.task.id: execution for execution in result.tasks}
    assert by_id["high"].start_time == 0
    assert by_id["low"].start_time == 10


def test_multi_resource_constraint_blocks_task() -> None:
    engine = SimulationEngine(
        EngineInput(
            run_id="run-blocked",
            tasks=[task("big", gpu=2)],
            servers=[server("s1", "A", gpu=1)],
            scheduler=scheduler(),
        )
    )
    result = engine.run()
    assert result.tasks[0].status == "BLOCKED"
    assert result.metrics["completion_rate"] == 0.0
    assert result.metrics["blocked_tasks"] == 1.0


def test_best_fit_prefers_tighter_server() -> None:
    candidate = task("t1")
    choice = choose_server(
        candidate,
        [server("large", "A", gpu=8), server("small", "B", gpu=2)],
        allocations={},
        placement_rule="BEST_FIT",
    )
    assert choice.server is not None
    assert choice.server.id == "small"


def test_first_fit_uses_stable_server_order() -> None:
    candidate = task("t1")
    choice = choose_server(
        candidate,
        [server("large", "A", gpu=8), server("small", "B", gpu=2)],
        allocations={},
        placement_rule="FIRST_FIT",
    )
    assert choice.server is not None
    assert choice.server.id == "large"


def test_simulation_is_reproducible() -> None:
    first = SimulationEngine(
        EngineInput(
            run_id="run-a",
            tasks=[task("t1"), task("t2", submit=2)],
            servers=[server("s1", "A")],
            scheduler=scheduler(),
        )
    ).run()
    second = SimulationEngine(
        EngineInput(
            run_id="run-b",
            tasks=[task("t1"), task("t2", submit=2)],
            servers=[server("s1", "A")],
            scheduler=scheduler(),
        )
    ).run()

    assert first.result_hash == second.result_hash
    assert [(e.event_time, e.event_type) for e in first.events] == [
        (e.event_time, e.event_type) for e in second.events
    ]


def test_step_by_step_matches_batch_run() -> None:
    tasks = [task("t1", duration=5), task("t2", submit=2, duration=3)]
    servers = [server("s1", "A")]
    config = scheduler()
    batch_result = SimulationEngine(
        EngineInput(run_id="batch", tasks=tasks, servers=servers, scheduler=config)
    ).run()

    stepped = SimulationEngine(
        EngineInput(run_id="stepped", tasks=tasks, servers=servers, scheduler=config)
    )
    stepped.initialize()
    step_count = 0
    while not stepped.finished:
        stepped.step()
        step_count += 1
    stepped_result = stepped.result()

    assert step_count > 1
    assert stepped_result.result_hash == batch_result.result_hash
    assert stepped_result.metrics == batch_result.metrics
