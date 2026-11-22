"""Audit key coverage between Alibaba GPU trace tables using chunked reads."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT = PROJECT_ROOT / "reports" / "data_relationships.json"
CHUNK_SIZE = 200_000

TABLE_KEYS: dict[str, dict[str, list[str]]] = {
    "pai_job_table": {
        "job.job_name": ["job_name"],
        "job.inst_id": ["inst_id"],
    },
    "pai_task_table": {
        "task.job_name": ["job_name"],
        "task.job+task": ["job_name", "task_name"],
    },
    "pai_instance_table": {
        "instance.job_name": ["job_name"],
        "instance.job+task": ["job_name", "task_name"],
        "instance.inst_id": ["inst_id"],
        "instance.worker_name": ["worker_name"],
        "instance.machine": ["machine"],
    },
    "pai_sensor_table": {
        "sensor.job_name": ["job_name"],
        "sensor.job+task": ["job_name", "task_name"],
        "sensor.inst_id": ["inst_id"],
        "sensor.worker_name": ["worker_name"],
        "sensor.machine": ["machine"],
    },
    "pai_group_tag_table": {
        "group.inst_id": ["inst_id"],
    },
    "pai_machine_spec": {
        "spec.machine": ["machine"],
    },
    "pai_machine_metric": {
        "metric.worker_name": ["worker_name"],
        "metric.machine": ["machine"],
    },
}

RELATIONSHIPS = [
    ("job.job_name", "task.job_name"),
    ("job.job_name", "instance.job_name"),
    ("job.job_name", "sensor.job_name"),
    ("job.inst_id", "group.inst_id"),
    ("job.inst_id", "instance.inst_id"),
    ("job.inst_id", "sensor.inst_id"),
    ("task.job+task", "instance.job+task"),
    ("task.job+task", "sensor.job+task"),
    ("instance.worker_name", "sensor.worker_name"),
    ("instance.worker_name", "metric.worker_name"),
    ("instance.machine", "sensor.machine"),
    ("instance.machine", "metric.machine"),
    ("spec.machine", "instance.machine"),
    ("spec.machine", "metric.machine"),
]


def collect_hashes(table: str, key_specs: dict[str, list[str]]) -> dict[str, np.ndarray]:
    path = DATA_DIR / table / f"{table}.csv"
    columns = sorted({column for cols in key_specs.values() for column in cols})
    chunks: dict[str, list[np.ndarray]] = {name: [] for name in key_specs}
    for chunk in pd.read_csv(
        path,
        header=None,
        names=TABLE_KEY_COLUMNS[table],
        usecols=columns,
        dtype={column: "string" for column in TABLE_KEY_COLUMNS[table]},
        chunksize=CHUNK_SIZE,
        low_memory=False,
    ):
        for key_name, cols in key_specs.items():
            subset = chunk[cols].dropna()
            if subset.empty:
                continue
            hashes = pd.util.hash_pandas_object(subset, index=False).to_numpy(
                dtype=np.uint64, copy=False
            )
            chunks[key_name].append(hashes)
    return {
        key_name: np.unique(np.concatenate(parts)) if parts else np.empty(0, dtype=np.uint64)
        for key_name, parts in chunks.items()
    }


TABLE_KEY_COLUMNS: dict[str, list[str]] = {
    "pai_job_table": ["job_name", "inst_id", "user", "status", "start_time", "end_time"],
    "pai_task_table": [
        "job_name", "task_name", "inst_num", "status", "start_time", "end_time",
        "plan_cpu", "plan_mem", "plan_gpu", "gpu_type",
    ],
    "pai_instance_table": [
        "job_name", "task_name", "inst_name", "worker_name", "inst_id",
        "status", "start_time", "end_time", "machine",
    ],
    "pai_sensor_table": [
        "job_name", "task_name", "worker_name", "inst_id", "machine",
        "gpu_name", "cpu_usage", "gpu_wrk_util", "avg_mem", "max_mem",
        "avg_gpu_wrk_mem", "max_gpu_wrk_mem", "read", "write", "read_count",
        "write_count",
    ],
    "pai_group_tag_table": ["inst_id", "user", "gpu_type_spec", "group", "workload"],
    "pai_machine_spec": ["machine", "gpu_type", "cap_cpu", "cap_mem", "cap_gpu"],
    "pai_machine_metric": [
        "worker_name", "machine", "start_time", "end_time",
        "machine_cpu_iowait", "machine_cpu_kernel", "machine_cpu_usr",
        "machine_gpu", "machine_load_1", "machine_net_receive",
        "machine_num_worker", "machine_cpu",
    ],
}


def main() -> int:
    key_hashes: dict[str, np.ndarray] = {}
    for table, specs in TABLE_KEYS.items():
        print(f"Collecting keys from {table} ...", flush=True)
        key_hashes.update(collect_hashes(table, specs))

    results = []
    for left, right in RELATIONSHIPS:
        left_values = key_hashes[left]
        right_values = key_hashes[right]
        common = np.intersect1d(left_values, right_values, assume_unique=True).size
        results.append(
            {
                "left": left,
                "right": right,
                "left_unique_non_null": int(left_values.size),
                "right_unique_non_null": int(right_values.size),
                "matched": int(common),
                "left_only": int(left_values.size - common),
                "right_only": int(right_values.size - common),
                "left_coverage_pct": round(common / left_values.size * 100, 4)
                if left_values.size
                else None,
                "right_coverage_pct": round(common / right_values.size * 100, 4)
                if right_values.size
                else None,
            }
        )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(
            {
                "method": (
                    "Non-null key columns are hashed in chunks and compared by "
                    "unique 64-bit hashes. Collisions are theoretically possible "
                    "but negligible."
                ),
                "relationships": results,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    for result in results:
        print(
            f"{result['left']} -> {result['right']}: "
            f"left_only={result['left_only']:,}, right_only={result['right_only']:,}, "
            f"left_coverage={result['left_coverage_pct']}%"
        )
    print(f"Wrote {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
