"""Evidence-based rule engine for scheduling recommendations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


RULE_VERSION = "advisor-rules-v1"


@dataclass(frozen=True)
class ComparisonMetric:
    run_id: str
    preset: str
    metrics: dict[str, float | None]


@dataclass(frozen=True)
class Recommendation:
    recommendation_type: str
    severity: str
    summary: str
    reasoning: str
    evidence: tuple[dict[str, Any], ...]
    suggested_patch: dict[str, Any] = field(default_factory=dict)
    rule_version: str = RULE_VERSION


def _metric_evidence(run_id: str, name: str, value: Any, unit: str = "") -> dict[str, Any]:
    return {
        "kind": "RUN_METRIC",
        "run_id": run_id,
        "metric_name": name,
        "value": value,
        "unit": unit,
    }


def _task_evidence(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": "TASK_RESULT",
        "task_id": task.get("task_id"),
        "task_name": task.get("task_name"),
        "status": task.get("status"),
        "wait_time": task.get("wait_time"),
        "gpu_required": task.get("gpu_required"),
        "gpu_type_required": task.get("gpu_type_required"),
    }


def analyze_run(
    *,
    run_id: str,
    current_preset: str,
    metrics: dict[str, float | None],
    wait_sla_seconds: int,
    tasks: list[dict[str, Any]],
    total_gpu_capacity: float,
    comparison_runs: list[ComparisonMetric] | None = None,
) -> list[Recommendation]:
    """Return deterministic, evidence-backed recommendations for one run."""
    recommendations: list[Recommendation] = []
    average_wait = metrics.get("average_wait_seconds")
    gpu_util = metrics.get("gpu_utilization")
    makespan = metrics.get("makespan_seconds")
    completion_rate = metrics.get("completion_rate")
    blocked = [task for task in tasks if task.get("status") == "BLOCKED"]

    if average_wait is not None and average_wait > wait_sla_seconds:
        evidence = [
            _metric_evidence(run_id, "average_wait_seconds", average_wait, "秒"),
            _metric_evidence(run_id, "wait_sla_seconds", wait_sla_seconds, "秒"),
            _metric_evidence(run_id, "completion_rate", completion_rate, "%"),
        ]
        recommendations.append(
            Recommendation(
                recommendation_type="HIGH_WAIT",
                severity="high" if average_wait > wait_sla_seconds * 1.5 else "medium",
                summary="任务排队等待超过配置的等待 SLA",
                reasoning=(
                    f"已完成任务平均等待 {average_wait:.1f} 秒，高于 SLA "
                    f"{wait_sla_seconds} 秒。应检查资源容量和任务排序，而不是只看完成率。"
                ),
                evidence=tuple(evidence),
                suggested_patch={
                    "review": "capacity_or_ordering",
                    "current_preset": current_preset,
                    "wait_sla_seconds": wait_sla_seconds,
                },
            )
        )

    if blocked:
        by_type: dict[str, list[dict[str, Any]]] = {}
        for task in blocked:
            key = str(task.get("gpu_type_required") or "ANY")
            by_type.setdefault(key, []).append(task)
        evidence = [_task_evidence(task) for task in blocked[:20]]
        capacity_patch = {
            gpu_type: round(
                sum(float(task.get("gpu_required") or 0) for task in grouped), 2
            )
            for gpu_type, grouped in by_type.items()
        }
        recommendations.append(
            Recommendation(
                recommendation_type="BLOCKED_TASKS",
                severity="high",
                summary=f"有 {len(blocked)} 个任务未获得资源",
                reasoning=(
                    "这些任务在仿真结束时仍处于 BLOCKED 状态。建议按缺失 GPU 型号增加容量，"
                    "或确认是否有意启用严格型号匹配。"
                ),
                evidence=tuple(evidence),
                suggested_patch={
                    "add_capacity_by_type": capacity_patch,
                    "review": "gpu_type_capacity",
                },
            )
        )

    if (
        gpu_util is not None
        and makespan is not None
        and makespan > 0
        and gpu_util < 0.30
    ):
        evidence = [
            _metric_evidence(run_id, "gpu_utilization", gpu_util, "%"),
            _metric_evidence(run_id, "makespan_seconds", makespan, "秒"),
            _metric_evidence(run_id, "total_gpu_capacity", total_gpu_capacity, "GPU 当量"),
        ]
        recommendations.append(
            Recommendation(
                recommendation_type="LOW_GPU_UTILIZATION",
                severity="low",
                summary="GPU 容量相对当前工作负载偏大",
                reasoning=(
                    f"GPU 时间加权平均利用率仅 {gpu_util:.1%}，同时 Makespan 为 "
                    f"{makespan:.0f} 秒。可评估缩减同型号容量、提高任务密度或使用更长的聚合工作负载。"
                ),
                evidence=tuple(evidence),
                suggested_patch={
                    "capacity_review": "reduce_or_consolidate",
                    "reviewed_gpu_utilization": gpu_util,
                },
            )
        )

    high_priority_waiting = [
        task
        for task in tasks
        if int(task.get("priority") or 0) >= 8
        and float(task.get("wait_time") or 0) > wait_sla_seconds
    ]
    if high_priority_waiting:
        recommendations.append(
            Recommendation(
                recommendation_type="PRIORITY_STARVATION",
                severity="medium",
                summary="高优先级任务等待超过 SLA",
                reasoning=(
                    f"有 {len(high_priority_waiting)} 个优先级不低于 8 的任务等待时间超过 "
                    f"{wait_sla_seconds} 秒。可评估 Priority 预设或预留容量。"
                ),
                evidence=tuple(_task_evidence(task) for task in high_priority_waiting[:20]),
                suggested_patch={"scheduler_preset_hint": "Priority"},
            )
        )

    fairness = metrics.get("fairness_index")
    if fairness is not None and fairness < 0.8:
        recommendations.append(
            Recommendation(
                recommendation_type="LOW_FAIRNESS",
                severity="medium",
                summary="用户维度 GPU 分配公平性偏低",
                reasoning=(
                    f"Jain 公平性指数为 {fairness:.4f}，低于 0.8。建议检查高优先级任务与容量"
                    "是否被少数用户长期占用，并评估公平性配额。"
                ),
                evidence=(
                    _metric_evidence(run_id, "fairness_index", fairness, "0-1"),
                ),
                suggested_patch={
                    "fairness_review": "consider_user_quotas",
                    "fairness_scope": "user",
                },
            )
        )

    if comparison_runs:
        eligible = [
            item
            for item in comparison_runs
            if (item.metrics.get("completion_rate") or 0.0)
            >= (completion_rate or 0.0) - 1e-9
            and item.metrics.get("average_wait_seconds") is not None
        ]
        if eligible:
            best = min(
                eligible,
                key=lambda item: (
                    item.metrics.get("average_wait_seconds") or float("inf"),
                    item.metrics.get("makespan_seconds") or float("inf"),
                    item.preset,
                ),
            )
            current_wait = average_wait or float("inf")
            best_wait = best.metrics.get("average_wait_seconds") or float("inf")
            if best.preset != current_preset and best_wait < current_wait * 0.98:
                recommendations.append(
                    Recommendation(
                        recommendation_type="STRATEGY_RECOMMENDATION",
                        severity="medium",
                        summary=f"可优先验证 {best.preset} 预设",
                        reasoning=(
                            f"{best.preset} 在相同输入下平均等待 {best_wait:.1f} 秒，"
                            f"低于当前 {current_preset} 的 {current_wait:.1f} 秒，且完成率不下降。"
                        ),
                        evidence=(
                            _metric_evidence(best.run_id, "average_wait_seconds", best_wait, "秒"),
                            _metric_evidence(run_id, "average_wait_seconds", current_wait, "秒"),
                            _metric_evidence(best.run_id, "completion_rate", best.metrics.get("completion_rate"), "%"),
                        ),
                        suggested_patch={"scheduler_preset_hint": best.preset},
                    )
                )

    if not recommendations:
        recommendations.append(
            Recommendation(
                recommendation_type="NO_ACTION",
                severity="info",
                summary="当前指标未触发异常规则",
                reasoning="等待、利用率、完成率、公平性和受阻任务均未超过当前规则阈值。",
                evidence=(
                    _metric_evidence(run_id, "average_wait_seconds", average_wait, "秒"),
                    _metric_evidence(run_id, "gpu_utilization", gpu_util, "%"),
                    _metric_evidence(run_id, "completion_rate", completion_rate, "%"),
                ),
                suggested_patch={},
            )
        )
    return recommendations
