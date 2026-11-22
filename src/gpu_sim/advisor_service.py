"""Application service for generating and applying advisory recommendations."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from gpu_sim.advisor import ComparisonMetric, Recommendation, analyze_run
from gpu_sim.compatibility import run_compatibility_key
from gpu_sim.db import Database
from gpu_sim.models import RecommendationRecord, SimulationRunRecord
from gpu_sim.services import recent_runs, run_task_rows, set_default_scheduler


def _task_dict(row, priority: int = 5) -> dict:
    return {
        "task_id": row.task_id,
        "task_name": row.task_name,
        "status": row.status,
        "wait_time": row.wait_time,
        "gpu_required": row.gpu_required,
        "cpu_required": row.cpu_required,
        "memory_required_gb": row.memory_required_gb,
        "gpu_type_required": row.gpu_type_required,
        "priority": priority,
    }


def generate_recommendations(database: Database, run_id: str) -> list[RecommendationRecord]:
    with database.session_scope() as session:
        run = session.get(SimulationRunRecord, run_id)
        if run is None:
            raise ValueError(f"Unknown simulation run: {run_id}")
        snapshot_priority = {
            str(task.get("id")): int(task.get("priority") or 5)
            for task in run.task_snapshot_json
        }
        tasks = [
            _task_dict(row, snapshot_priority.get(row.task_id, 5))
            for row in run_task_rows(session, run_id)
        ]
        total_gpu = sum(
            float(server.get("gpu_capacity") or 0)
            for server in run.server_snapshot_json
        )
        current_key = run_compatibility_key(run)
        compatible = [
            candidate
            for candidate in recent_runs(session, limit=100)
            if candidate.id != run.id and run_compatibility_key(candidate) == current_key
        ]
        comparisons = [
            ComparisonMetric(
                run_id=candidate.id,
                preset=candidate.scheduler_preset,
                metrics=candidate.metrics_json or {},
            )
            for candidate in compatible
        ]
        recommendations = analyze_run(
            run_id=run.id,
            current_preset=run.scheduler_preset,
            metrics=run.metrics_json or {},
            wait_sla_seconds=run.wait_sla_seconds,
            tasks=tasks,
            total_gpu_capacity=total_gpu,
            comparison_runs=comparisons,
        )

        session.execute(
            delete(RecommendationRecord).where(RecommendationRecord.run_id == run_id)
        )
        for recommendation in recommendations:
            session.add(
                RecommendationRecord(
                    id=f"rec-{uuid4().hex[:12]}",
                    run_id=run_id,
                    recommendation_type=recommendation.recommendation_type,
                    severity=recommendation.severity,
                    summary=recommendation.summary,
                    reasoning=recommendation.reasoning,
                    evidence_json=list(recommendation.evidence),
                    suggested_patch_json=recommendation.suggested_patch,
                    rule_version=recommendation.rule_version,
                )
            )
        session.flush()
        return list(
            session.scalars(
                select(RecommendationRecord)
                .where(RecommendationRecord.run_id == run_id)
                .order_by(RecommendationRecord.created_at, RecommendationRecord.id)
            )
        )


def list_recommendations(database: Database, run_id: str) -> list[RecommendationRecord]:
    with database.session_scope() as session:
        return list(
            session.scalars(
                select(RecommendationRecord)
                .where(RecommendationRecord.run_id == run_id)
                .order_by(RecommendationRecord.created_at, RecommendationRecord.id)
            )
        )


def accept_recommendation(database: Database, recommendation_id: str) -> None:
    with database.session_scope() as session:
        record = session.get(RecommendationRecord, recommendation_id)
        if record is None:
            raise ValueError(f"Unknown recommendation: {recommendation_id}")
        record.accepted = True


def apply_scheduler_hint(database: Database, recommendation_id: str) -> str:
    """Apply only an explicit scheduler preset hint, never a capacity mutation."""
    with database.session_scope() as session:
        record = session.get(RecommendationRecord, recommendation_id)
        if record is None:
            raise ValueError(f"Unknown recommendation: {recommendation_id}")
        run = session.get(SimulationRunRecord, record.run_id)
        if run is None:
            raise ValueError(f"Unknown simulation run: {record.run_id}")
        preset = record.suggested_patch_json.get("scheduler_preset_hint")
        if not preset:
            raise ValueError("This recommendation has no scheduler preset hint")
        set_default_scheduler(
            session,
            preset=str(preset),
            random_seed=run.random_seed,
            wait_sla_seconds=run.wait_sla_seconds,
            allow_skip_head=run.allow_skip_head,
        )
        record.accepted = True
        session.flush()
        return str(preset)
