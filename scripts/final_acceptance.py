"""Final end-to-end acceptance check for GPUFlow v1.0."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gpu_sim.advisor_service import generate_recommendations, list_recommendations  # noqa: E402
from gpu_sim.application import execute_strategy_batch, prepare_simulation  # noqa: E402
from gpu_sim.db import Database  # noqa: E402
from gpu_sim.importer import import_historical_workload_sample  # noqa: E402
from gpu_sim.services import database_counts, initialize_database  # noqa: E402
from gpu_sim.simulation import SimulationEngine  # noqa: E402


def main() -> int:
    path = ROOT / "artifacts" / "final-acceptance.db"
    for suffix in ("", "-wal", "-shm"):
        candidate = Path(str(path) + suffix)
        if candidate.exists():
            candidate.unlink()
    database = Database(path)
    try:
        initialize_database(database)
        with database.session_scope() as session:
            initial = database_counts(session)
        assert initial["servers"] == 7
        assert initial["user_tasks"] == 6

        dataset_id, imported_count = import_historical_workload_sample(
            database, task_limit=20
        )
        assert imported_count == 20

        user_batch = execute_strategy_batch(
            database,
            source="USER_CREATED",
            presets=["FIFO", "SJF", "Priority", "Best Fit"],
            random_seed=42,
            wait_sla_seconds=900,
            allow_skip_head=False,
            name_prefix="final user",
        )
        history_batch = execute_strategy_batch(
            database,
            source="HISTORICAL_REPLAY",
            presets=["FIFO", "SJF", "Priority", "Best Fit"],
            random_seed=42,
            wait_sla_seconds=900,
            allow_skip_head=False,
            name_prefix="final history",
        )
        assert len(user_batch.outcomes) == 4
        assert len(history_batch.outcomes) == 4
        assert len({item.result.result_hash for item in history_batch.outcomes}) == 4

        recommendations = generate_recommendations(
            database, history_batch.outcomes[0].run_id
        )
        assert recommendations
        assert list_recommendations(database, history_batch.outcomes[0].run_id)

        prepared = prepare_simulation(
            database,
            source="USER_CREATED",
            preset="FIFO",
            random_seed=42,
            wait_sla_seconds=900,
            allow_skip_head=False,
        )
        engine = SimulationEngine(prepared.engine_input)
        engine.initialize()
        steps = 0
        while not engine.finished:
            engine.step()
            steps += 1
        assert steps > 1
        assert engine.result().metrics["completion_rate"] == 1.0

        with database.session_scope() as session:
            final = database_counts(session)
        assert final["runs"] == 8
        print("FINAL_ACCEPTANCE_OK")
        print("history_dataset", dataset_id)
        print("history_tasks", imported_count)
        print("runs", final["runs"])
        print("recommendations", len(recommendations))
        print("live_steps", steps)
        print("sample_hash", history_batch.outcomes[0].result.result_hash)
        return 0
    finally:
        database.dispose()
        for suffix in ("", "-wal", "-shm"):
            candidate = Path(str(path) + suffix)
            if candidate.exists():
                candidate.unlink()


if __name__ == "__main__":
    raise SystemExit(main())
