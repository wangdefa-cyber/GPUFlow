from __future__ import annotations

from copy import deepcopy

from gpu_sim.prototype.logic import (
    DEFAULT_SERVERS,
    DEFAULT_TASKS,
    capacity_summary,
    defaults,
    order_tasks,
    preflight_tasks,
    server_can_fit,
    simulation_readiness,
    validate_servers,
    validate_tasks,
)


def test_defaults_are_valid_and_independent() -> None:
    servers, tasks, scheduler = defaults()

    assert validate_servers(servers) == []
    assert validate_tasks(tasks) == []
    assert scheduler["preset"] == "FIFO"

    servers[0]["name"] = "mutated"
    assert DEFAULT_SERVERS[0]["name"] != "mutated"


def test_capacity_summary_counts_only_active_servers() -> None:
    servers = deepcopy(DEFAULT_SERVERS)
    servers[-1]["status"] = "Disabled"

    summary = capacity_summary(servers)

    assert summary.server_count == 7
    assert summary.active_server_count == 6
    assert summary.total_gpu == 24


def test_fifo_ordering_uses_arrival_then_sequence() -> None:
    tasks = deepcopy(DEFAULT_TASKS)
    ordered = order_tasks(list(reversed(tasks)), "FIFO")

    assert [task["submit_time"] for task in ordered] == sorted(task["submit_time"] for task in ordered)


def test_priority_ordering_uses_descending_priority() -> None:
    ordered = order_tasks(deepcopy(DEFAULT_TASKS), "Priority")

    assert ordered[0]["priority"] == 9


def test_preflight_accepts_default_configuration() -> None:
    rows = preflight_tasks(deepcopy(DEFAULT_TASKS), deepcopy(DEFAULT_SERVERS))

    assert rows
    assert all(row["预检结果"] == "可容纳" for row in rows)


def test_server_type_must_match() -> None:
    task = {"gpu_required": 1, "cpu_required": 2, "memory_required_gb": 4, "gpu_type_required": "T4"}
    server = {
        "gpu_type": "P100",
        "gpu_capacity": 8,
        "cpu_capacity": 96,
        "memory_capacity_gb": 512,
        "status": "Active",
    }

    assert server_can_fit(server, task) is False


def test_server_validation_rejects_duplicate_names_and_negative_values() -> None:
    servers = deepcopy(DEFAULT_SERVERS)
    servers[1]["name"] = servers[0]["name"]
    servers[1]["cpu_capacity"] = -1

    errors = validate_servers(servers)

    assert any("名称重复" in error for error in errors)
    assert any("不能为负数" in error for error in errors)


def test_task_validation_rejects_zero_duration() -> None:
    tasks = deepcopy(DEFAULT_TASKS)
    tasks[0]["estimated_duration"] = 0

    errors = validate_tasks(tasks)

    assert any("预计运行时长必须大于 0" in error for error in errors)


def test_readiness_explicitly_keeps_engine_at_stage_four() -> None:
    checks = simulation_readiness(
        deepcopy(DEFAULT_SERVERS), deepcopy(DEFAULT_TASKS), {"preset": "FIFO"}
    )

    engine = next(row for row in checks if row["检查项"] == "仿真引擎")
    assert engine["状态"] == "阶段 4"
