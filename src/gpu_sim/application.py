"""Application orchestration for running and persisting a simulation."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from gpu_sim.db import Database
from gpu_sim.domain import SimulationResult
from gpu_sim.services import (
    list_servers,
    save_simulation_result,
    scheduler_dicts,
    scheduler_spec,
    task_dicts,
    to_server_specs,
    to_task_specs,
)
from gpu_sim.simulation import EngineInput, SimulationEngine


@dataclass(frozen=True)
class RunOutcome:
    result: SimulationResult
    run_id: str
    workload_label: str
    task_count: int
    server_count: int


def execute_simulation(
    database: Database,
    source: str,
    preset: str,
    random_seed: int,
    wait_sla_seconds: int,
    allow_skip_head: bool,
    run_name: str,
) -> RunOutcome:
    """Load frozen inputs, run the engine, and persist the complete result."""
    with database.session_scope() as session:
        servers = to_server_specs(list_servers(session))
        tasks, dataset = task_dicts(session, source)
        configs = scheduler_dicts(session)
        config = next((row for row in configs if row["preset"] == preset), None)
        if config is None:
            raise ValueError(f"Unknown scheduler preset: {preset}")
        config = {
            **config,
            "random_seed": int(random_seed),
            "wait_sla_seconds": int(wait_sla_seconds),
            "allow_skip_head": bool(allow_skip_head),
        }
        scheduler = scheduler_spec(config)
        if not tasks:
            raise ValueError("Selected workload has no active tasks")
        if not servers:
            raise ValueError("No GPU server configuration exists")

        run_id = f"run-{uuid4().hex[:12]}"
        task_specs = to_task_specs(tasks)
        engine = SimulationEngine(
            EngineInput(
                run_id=run_id,
                tasks=task_specs,
                servers=servers,
                scheduler=scheduler,
            )
        )
        result = engine.run()

        if source == "HISTORICAL_REPLAY" and dataset is not None:
            workload_label = f"真实历史样本 · {dataset.version_code}"
        else:
            workload_label = "用户创建任务"
        save_simulation_result(
            session=session,
            result=result,
            run_name=run_name.strip() or "未命名实验",
            workload_label=workload_label,
            task_snapshot=[task.as_dict() for task in task_specs],
            server_snapshot=[server.as_dict() for server in servers],
        )
        return RunOutcome(
            result=result,
            run_id=run_id,
            workload_label=workload_label,
            task_count=len(tasks),
            server_count=len(servers),
        )
