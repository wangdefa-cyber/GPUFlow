"""Repeatable stage 6 advisory smoke test."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gpu_sim.advisor_service import generate_recommendations  # noqa: E402
from gpu_sim.application import execute_strategy_batch  # noqa: E402
from gpu_sim.db import Database  # noqa: E402
from gpu_sim.services import initialize_database  # noqa: E402


def main() -> int:
    path = ROOT / "artifacts" / "stage6-smoke.db"
    if path.exists():
        path.unlink()
    database = Database(path)
    try:
        initialize_database(database)
        batch = execute_strategy_batch(
            database=database,
            source="USER_CREATED",
            presets=["FIFO", "SJF", "Priority", "Best Fit"],
            random_seed=42,
            wait_sla_seconds=900,
            allow_skip_head=False,
            name_prefix="stage6 smoke",
        )
        recommendations = generate_recommendations(
            database, batch.outcomes[0].run_id
        )
        print("run", batch.outcomes[0].run_id)
        for recommendation in recommendations:
            print(
                recommendation.recommendation_type,
                recommendation.severity,
                recommendation.summary,
                "evidence", len(recommendation.evidence_json),
            )
        assert recommendations
        assert all(item.evidence_json for item in recommendations)
        return 0
    finally:
        database.dispose()
        for suffix in ("", "-wal", "-shm"):
            candidate = Path(str(path) + suffix)
            if candidate.exists():
                candidate.unlink()


if __name__ == "__main__":
    raise SystemExit(main())
