"""Repeatable stage 5 strategy-comparison smoke test."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gpu_sim.application import execute_strategy_batch  # noqa: E402
from gpu_sim.db import Database  # noqa: E402
from gpu_sim.importer import import_historical_workload_sample  # noqa: E402
from gpu_sim.services import initialize_database  # noqa: E402


def main() -> int:
    path = ROOT / "artifacts" / "stage5-smoke.db"
    if path.exists():
        path.unlink()
    database = Database(path)
    try:
        initialize_database(database)
        import_historical_workload_sample(database, task_limit=20)
        for source in ("USER_CREATED", "HISTORICAL_REPLAY"):
            batch = execute_strategy_batch(
                database=database,
                source=source,
                presets=["FIFO", "SJF", "Priority", "Best Fit"],
                random_seed=42,
                wait_sla_seconds=900,
                allow_skip_head=False,
                name_prefix=f"stage5-{source}",
            )
            print(f"\n{source} · {batch.workload_label}")
            for outcome in batch.outcomes:
                metrics = outcome.result.metrics
                print(
                    outcome.result.config.preset.ljust(9),
                    "wait", round(metrics["average_wait_seconds"] or 0, 2),
                    "makespan", round(metrics["makespan_seconds"] or 0, 2),
                    "gpu%", round((metrics["gpu_utilization"] or 0) * 100, 3),
                    "complete%", round((metrics["completion_rate"] or 0) * 100, 2),
                    "fairness", round(metrics["fairness_index"] or 0, 4),
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
