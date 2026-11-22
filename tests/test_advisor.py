from __future__ import annotations

from gpu_sim.advisor import ComparisonMetric, analyze_run


def task(task_id: str, *, status: str = "COMPLETED", wait: float = 10.0, gpu: float = 1.0, gpu_type: str = "V100", priority: int = 5) -> dict:
    return {
        "task_id": task_id,
        "task_name": task_id,
        "status": status,
        "wait_time": wait,
        "gpu_required": gpu,
        "gpu_type_required": gpu_type,
        "priority": priority,
    }


def test_high_wait_blocked_and_fairness_rules_have_evidence() -> None:
    recommendations = analyze_run(
        run_id="run-1",
        current_preset="FIFO",
        metrics={
            "average_wait_seconds": 2000.0,
            "gpu_utilization": 0.9,
            "makespan_seconds": 4000.0,
            "completion_rate": 0.5,
            "fairness_index": 0.4,
            "blocked_tasks": 1.0,
        },
        wait_sla_seconds=900,
        tasks=[task("blocked", status="BLOCKED", wait=2000, gpu=2, gpu_type="V100")],
        total_gpu_capacity=8.0,
    )
    types = {item.recommendation_type for item in recommendations}
    assert {"HIGH_WAIT", "BLOCKED_TASKS", "LOW_FAIRNESS"} <= types
    assert all(item.evidence for item in recommendations)
    blocked = next(item for item in recommendations if item.recommendation_type == "BLOCKED_TASKS")
    assert blocked.suggested_patch["add_capacity_by_type"]["V100"] == 2.0


def test_low_utilization_rule_is_reported() -> None:
    recommendations = analyze_run(
        run_id="run-low",
        current_preset="FIFO",
        metrics={
            "average_wait_seconds": 10.0,
            "gpu_utilization": 0.05,
            "makespan_seconds": 50000.0,
            "completion_rate": 1.0,
            "fairness_index": 0.95,
            "blocked_tasks": 0.0,
        },
        wait_sla_seconds=900,
        tasks=[],
        total_gpu_capacity=32.0,
    )
    assert any(item.recommendation_type == "LOW_GPU_UTILIZATION" for item in recommendations)


def test_comparison_can_recommend_better_strategy() -> None:
    recommendations = analyze_run(
        run_id="run-fifo",
        current_preset="FIFO",
        metrics={
            "average_wait_seconds": 100.0,
            "gpu_utilization": 0.5,
            "makespan_seconds": 1000.0,
            "completion_rate": 1.0,
            "fairness_index": 0.9,
            "blocked_tasks": 0.0,
        },
        wait_sla_seconds=900,
        tasks=[],
        total_gpu_capacity=8.0,
        comparison_runs=[
            ComparisonMetric(
                run_id="run-sjf",
                preset="SJF",
                metrics={
                    "average_wait_seconds": 50.0,
                    "makespan_seconds": 1000.0,
                    "completion_rate": 1.0,
                },
            )
        ],
    )
    strategy = next(
        item for item in recommendations if item.recommendation_type == "STRATEGY_RECOMMENDATION"
    )
    assert strategy.suggested_patch["scheduler_preset_hint"] == "SJF"
    assert any(item["run_id"] == "run-sjf" for item in strategy.evidence)


def test_no_action_rule_when_metrics_are_healthy() -> None:
    recommendations = analyze_run(
        run_id="run-healthy",
        current_preset="FIFO",
        metrics={
            "average_wait_seconds": 10.0,
            "gpu_utilization": 0.75,
            "makespan_seconds": 1000.0,
            "completion_rate": 1.0,
            "fairness_index": 0.95,
            "blocked_tasks": 0.0,
        },
        wait_sla_seconds=900,
        tasks=[],
        total_gpu_capacity=8.0,
    )
    assert recommendations[0].recommendation_type == "NO_ACTION"
