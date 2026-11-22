from __future__ import annotations

from pathlib import Path
from shutil import rmtree
from uuid import uuid4

from gpu_sim.application import execute_simulation
from gpu_sim.db import Database
from gpu_sim.models import SimulationRunRecord
from gpu_sim.services import (
    database_counts,
    initialize_database,
    run_sample_rows,
    run_task_rows,
    scheduler_dicts,
    server_dicts,
    task_dicts,
    user_task_dicts,
)


def test_database_seed_and_closed_loop() -> None:
    artifact_dir = Path(__file__).resolve().parents[1] / "artifacts" / "test-db"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    case_dir = artifact_dir / uuid4().hex
    case_dir.mkdir(parents=True)
    database = Database(case_dir / "gpuflow.db")
    try:
        initialize_database(database)

        with database.session_scope() as session:
            counts = database_counts(session)
            assert counts["servers"] == 7
            assert counts["user_tasks"] == 6
            assert counts["runs"] == 0
            assert len(server_dicts(session)) == 7
            assert len(user_task_dicts(session)) == 6
            assert scheduler_dicts(session)

        outcome = execute_simulation(
            database=database,
            source="USER_CREATED",
            preset="FIFO",
            random_seed=42,
            wait_sla_seconds=900,
            allow_skip_head=False,
            run_name="integration run",
        )

        assert outcome.task_count == 6
        assert outcome.server_count == 7
        assert outcome.result.result_hash

        with database.session_scope() as session:
            counts = database_counts(session)
            assert counts["runs"] == 1
            tasks = run_task_rows(session, outcome.run_id)
            samples = run_sample_rows(session, outcome.run_id)
            run = session.get(SimulationRunRecord, outcome.run_id)
            assert run is not None
            assert run.result_hash == outcome.result.result_hash
            assert tasks
            assert samples
            assert any(row.status == "COMPLETED" for row in tasks)
            historical, dataset = task_dicts(session, "HISTORICAL_REPLAY")
            assert historical == []
            assert dataset is None
    finally:
        database.dispose()
        rmtree(case_dir, ignore_errors=True)
