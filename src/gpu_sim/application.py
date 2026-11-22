"""Application orchestration for single runs, steppable runs, and strategy batches."""

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
class PreparedSimulation:
    engine_input: EngineInput
    task_snapshot: list[dict]
    server_snapshot: list[dict]
    workload_label: str
    task_count: int
    server_count: int


@dataclass(frozen=True)
class RunOutcome:
    result: SimulationResult
    run_id: str
    workload_label: str
    task_count: int
    server_count: int


@dataclass(frozen=True)
class StrategyBatchOutcome:
    outcomes: tuple[RunOutcome, ...]
    workload_label: str


def _resolve_config(
    configs: list[dict],
    preset: str,
    random_seed: int,
    wait_sla_seconds: int,
    allow_skip_head: bool,
) -> dict:
    config = next((row for row in configs if row["preset"] == preset), None)
    if config is None:
        raise ValueError(f"Unknown scheduler preset: {preset}")
    return {
        **config,
        "random_seed": int(random_seed),
        "wait_sla_seconds": int(wait_sla_seconds),
        "allow_skip_head": bool(allow_skip_head),
    }


def prepare_simulation(
    database: Database,
    source: str,
    preset: str,
    random_seed: int,
    wait_sla_seconds: int,
    allow_skip_head: bool,
) -> PreparedSimulation:
    """Freeze workload, cluster, and scheduler input for one deterministic run."""
    with database.session_scope() as session:
        servers = to_server_specs(list_servers(session))
        tasks, dataset = task_dicts(session, source)
        configs = scheduler_dicts(session)
        if not tasks:
            raise ValueError("Selected workload has no active tasks")
        if not servers:
            raise ValueError("No GPU server configuration exists")
        config = _resolve_config(
            configs, preset, random_seed, wait_sla_seconds, allow_skip_head
        )
        task_specs = to_task_specs(tasks)
        run_id = f"run-{uuid4().hex[:12]}"
        workload_label = (
            f"真实历史样本 · {dataset.version_code}"
            if source == "HISTORICAL_REPLAY" and dataset is not None
            else "用户创建任务"
        )
        return PreparedSimulation(
            engine_input=EngineInput(
                run_id=run_id,
                tasks=task_specs,
                servers=servers,
                scheduler=scheduler_spec(config),
            ),
            task_snapshot=[task.as_dict() for task in task_specs],
            server_snapshot=[server.as_dict() for server in servers],
            workload_label=workload_label,
            task_count=len(task_specs),
            server_count=len(servers),
        )


def persist_simulation_result(
    database: Database,
    prepared: PreparedSimulation,
    result: SimulationResult,
    run_name: str,
) -> str:
    with database.session_scope() as session:
        return save_simulation_result(
            session=session,
            result=result,
            run_name=run_name.strip() or "未命名实验",
            workload_label=prepared.workload_label,
            task_snapshot=prepared.task_snapshot,
            server_snapshot=prepared.server_snapshot,
        )


def execute_simulation(
    database: Database,
    source: str,
    preset: str,
    random_seed: int,
    wait_sla_seconds: int,
    allow_skip_head: bool,
    run_name: str,
) -> RunOutcome:
    prepared = prepare_simulation(
        database,
        source,
        preset,
        random_seed,
        wait_sla_seconds,
        allow_skip_head,
    )
    result = SimulationEngine(prepared.engine_input).run()
    persist_simulation_result(database, prepared, result, run_name)
    return RunOutcome(
        result=result,
        run_id=prepared.engine_input.run_id,
        workload_label=prepared.workload_label,
        task_count=prepared.task_count,
        server_count=prepared.server_count,
    )


def execute_strategy_batch(
    database: Database,
    source: str,
    presets: list[str],
    random_seed: int,
    wait_sla_seconds: int,
    allow_skip_head: bool,
    name_prefix: str,
) -> StrategyBatchOutcome:
    """Run all presets against one frozen task/server snapshot and seed."""
    with database.session_scope() as session:
        servers = to_server_specs(list_servers(session))
        tasks, dataset = task_dicts(session, source)
        configs = scheduler_dicts(session)
        if not tasks:
            raise ValueError("Selected workload has no active tasks")
        if not servers:
            raise ValueError("No GPU server configuration exists")
        task_specs = to_task_specs(tasks)
        task_snapshot = [task.as_dict() for task in task_specs]
        server_snapshot = [server.as_dict() for server in servers]
        workload_label = (
            f"真实历史样本 · {dataset.version_code}"
            if source == "HISTORICAL_REPLAY" and dataset is not None
            else "用户创建任务"
        )

        outcomes: list[RunOutcome] = []
        for preset in presets:
            config = _resolve_config(
                configs, preset, random_seed, wait_sla_seconds, allow_skip_head
            )
            run_id = f"run-{uuid4().hex[:12]}"
            result = SimulationEngine(
                EngineInput(
                    run_id=run_id,
                    tasks=task_specs,
                    servers=servers,
                    scheduler=scheduler_spec(config),
                )
            ).run()
            save_simulation_result(
                session=session,
                result=result,
                run_name=f"{name_prefix.strip() or '策略对比'} · {preset}",
                workload_label=workload_label,
                task_snapshot=task_snapshot,
                server_snapshot=server_snapshot,
            )
            outcomes.append(
                RunOutcome(
                    result=result,
                    run_id=run_id,
                    workload_label=workload_label,
                    task_count=len(task_specs),
                    server_count=len(servers),
                )
            )
        session.flush()
        return StrategyBatchOutcome(
            outcomes=tuple(outcomes), workload_label=workload_label
        )
