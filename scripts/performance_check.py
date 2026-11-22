"""Performance check for the deterministic simulation engine.

The workload is synthetic and used only for performance measurement.
It is never written to the application database or presented as real data.
"""

from __future__ import annotations

import random
import sys
import time
import tracemalloc
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gpu_sim.domain import ResourceVector, SchedulerSpec, ServerSpec, TaskSpec  # noqa: E402
from gpu_sim.simulation import EngineInput, SimulationEngine  # noqa: E402


def build_case(task_count: int = 1000, server_count: int = 20):
    rng = random.Random(20261122)
    servers = [
        ServerSpec(
            id=f"perf-server-{index:03d}",
            name=f"V100-{index:03d}",
            gpu_type="V100",
            capacity=ResourceVector(gpu=8, cpu=96, memory_gb=512),
        )
        for index in range(server_count)
    ]
    tasks = [
        TaskSpec(
            id=f"perf-task-{index:05d}",
            name=f"task-{index:05d}",
            submit_time=float(rng.randint(0, 3600)),
            priority=rng.randint(1, 10),
            estimated_duration=float(rng.randint(120, 7200)),
            demand=ResourceVector(
                gpu=float(rng.choice([0.5, 1, 2, 4])),
                cpu=float(rng.choice([2, 4, 8, 16, 24])),
                memory_gb=float(rng.choice([8, 16, 32, 64])),
            ),
            gpu_type_required="V100",
            source_type="PERFORMANCE_TEST",
            user_key=f"user-{index % 20}",
            sequence_no=index,
        )
        for index in range(task_count)
    ]
    return tasks, servers


def main() -> int:
    tasks, servers = build_case()
    for preset, order_rule, placement_rule in (
        ("FIFO", "FIFO", "FIRST_FIT"),
        ("SJF", "SJF", "FIRST_FIT"),
        ("Priority", "PRIORITY", "FIRST_FIT"),
        ("Best Fit", "FIFO", "BEST_FIT"),
    ):
        tracemalloc.start()
        started = time.perf_counter()
        result = SimulationEngine(
            EngineInput(
                run_id=f"perf-{preset}",
                tasks=tasks,
                servers=servers,
                scheduler=SchedulerSpec(
                    preset=preset,
                    order_rule=order_rule,
                    placement_rule=placement_rule,
                    random_seed=20261122,
                    wait_sla_seconds=900,
                    allow_skip_head=False,
                ),
            )
        ).run()
        elapsed = time.perf_counter() - started
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        print(
            preset.ljust(9),
            f"seconds={elapsed:.4f}",
            f"tasks_per_second={len(tasks) / elapsed:,.0f}",
            f"peak_mb={peak / 1024 / 1024:.2f}",
            f"events={len(result.events):,}",
            f"completed={result.metrics['completed_tasks']:.0f}",
            f"blocked={result.metrics['blocked_tasks']:.0f}",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
