"""Repeatable stage 4 closed-loop smoke test."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gpu_sim.application import execute_simulation  # noqa: E402
from gpu_sim.db import Database  # noqa: E402
from gpu_sim.importer import import_historical_workload_sample  # noqa: E402
from gpu_sim.services import initialize_database  # noqa: E402


def main() -> int:
    path = ROOT / "artifacts" / "stage4-smoke.db"
    if path.exists():
        path.unlink()
    database = Database(path)
    try:
        initialize_database(database)
        dataset_id, imported = import_historical_workload_sample(
            database, task_limit=20, progress=lambda message: print(message)
        )
        print("historical dataset", dataset_id, "tasks", imported)

        user_run = execute_simulation(
            database=database,
            source="USER_CREATED",
            preset="SJF",
            random_seed=42,
            wait_sla_seconds=900,
            allow_skip_head=False,
            run_name="smoke user tasks",
        )
        history_run = execute_simulation(
            database=database,
            source="HISTORICAL_REPLAY",
            preset="FIFO",
            random_seed=42,
            wait_sla_seconds=900,
            allow_skip_head=False,
            run_name="smoke historical replay",
        )
        for label, outcome in (("user", user_run), ("history", history_run)):
            metrics = outcome.result.metrics
            print(
                label,
                "tasks", outcome.task_count,
                "hash", outcome.result.result_hash[:16],
                "wait", metrics["average_wait_seconds"],
                "makespan", metrics["makespan_seconds"],
                "gpu", metrics["gpu_utilization"],
                "complete", metrics["completion_rate"],
                "blocked", metrics["blocked_tasks"],
            )
        return 0
    finally:
        database.dispose()
        for suffix in ("", "-wal", "-shm"):
            candidate = Path(str(path) + suffix)
            if candidate.exists():
                candidate.unlink()


if __name__ == "__main__":
    raise SystemExit(main())
