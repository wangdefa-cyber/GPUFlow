"""Targeted quality checks that require relationships or status-aware logic."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT = PROJECT_ROOT / "reports" / "data_quality_checks.json"
CHUNK_SIZE = 200_000

SCHEMAS = {
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
    "pai_machine_spec": ["machine", "gpu_type", "cap_cpu", "cap_mem", "cap_gpu"],
    "pai_machine_metric": [
        "worker_name", "machine", "start_time", "end_time",
        "machine_cpu_iowait", "machine_cpu_kernel", "machine_cpu_usr",
        "machine_gpu", "machine_load_1", "machine_net_receive",
        "machine_num_worker", "machine_cpu",
    ],
}

STATUS_FIELDS = {
    "pai_job_table": ["start_time", "end_time"],
    "pai_task_table": ["start_time", "end_time", "plan_cpu", "plan_mem", "plan_gpu", "gpu_type"],
    "pai_instance_table": ["start_time", "end_time", "worker_name", "machine"],
}


def string_dtypes(table: str) -> dict[str, str]:
    columns = SCHEMAS[table]
    numeric = {
        "start_time", "end_time", "inst_num", "plan_cpu", "plan_mem", "plan_gpu",
        "cpu_usage", "gpu_wrk_util", "avg_mem", "max_mem", "avg_gpu_wrk_mem",
        "max_gpu_wrk_mem", "read", "write", "read_count", "write_count",
        "cap_cpu", "cap_mem", "cap_gpu", "machine_cpu_iowait",
        "machine_cpu_kernel", "machine_cpu_usr", "machine_gpu", "machine_load_1",
        "machine_net_receive", "machine_num_worker", "machine_cpu",
    }
    return {column: ("float64" if column in numeric else "string") for column in columns}


def status_completeness(table: str) -> dict[str, dict[str, int]]:
    path = DATA_DIR / table / f"{table}.csv"
    fields = STATUS_FIELDS[table]
    result: dict[str, dict[str, int]] = {}
    for chunk in pd.read_csv(
        path, header=None, names=SCHEMAS[table], dtype=string_dtypes(table),
        chunksize=CHUNK_SIZE, low_memory=False,
    ):
        statuses = chunk["status"].fillna("<NULL>").astype(str)
        for status in statuses.unique():
            mask = statuses == status
            target = result.setdefault(status, {"rows": 0})
            target["rows"] += int(mask.sum())
            for field in fields:
                key = f"missing_{field}"
                target[key] = target.get(key, 0) + int(chunk.loc[mask, field].isna().sum())
    return result


def task_missing_matrix() -> dict[str, dict[str, int]]:
    path = DATA_DIR / "pai_task_table" / "pai_task_table.csv"
    counter: Counter[tuple[str, bool, bool]] = Counter()
    for chunk in pd.read_csv(
        path, header=None, names=SCHEMAS["pai_task_table"],
        dtype=string_dtypes("pai_task_table"), chunksize=CHUNK_SIZE, low_memory=False,
    ):
        gpu_types = chunk["gpu_type"].fillna("<NULL>").astype(str)
        gpu_missing = chunk["plan_gpu"].isna().tolist()
        type_missing = chunk["gpu_type"].isna().tolist()
        counter.update(zip(gpu_types, gpu_missing, type_missing))
    return {
        f"gpu_type={gpu_type}|plan_gpu_missing={plan_missing}|gpu_type_missing={type_missing}": count
        for (gpu_type, plan_missing, type_missing), count in sorted(counter.items())
    }


def task_resource_quantiles() -> dict[str, dict[str, float | int]]:
    path = DATA_DIR / "pai_task_table" / "pai_task_table.csv"
    arrays: dict[str, list[np.ndarray]] = {
        "plan_cpu": [], "plan_mem": [], "plan_gpu": [], "duration": []
    }
    for chunk in pd.read_csv(
        path, header=None, names=SCHEMAS["pai_task_table"],
        dtype=string_dtypes("pai_task_table"), chunksize=CHUNK_SIZE, low_memory=False,
    ):
        for column in ("plan_cpu", "plan_mem", "plan_gpu"):
            arrays[column].append(chunk[column].dropna().to_numpy(dtype=float))
        valid = chunk[["start_time", "end_time"]].dropna()
        arrays["duration"].append((valid["end_time"] - valid["start_time"]).to_numpy(dtype=float))

    output = {}
    for name, parts in arrays.items():
        values = np.concatenate(parts)
        output[name] = {
            "count": int(values.size),
            "p50": float(np.quantile(values, 0.50)),
            "p90": float(np.quantile(values, 0.90)),
            "p95": float(np.quantile(values, 0.95)),
            "p99": float(np.quantile(values, 0.99)),
            "max": float(values.max()),
        }
    return output


def machine_gpu_normalization() -> dict[str, float | int | None]:
    spec_path = DATA_DIR / "pai_machine_spec" / "pai_machine_spec.csv"
    spec = pd.read_csv(
        spec_path, header=None, names=SCHEMAS["pai_machine_spec"],
        dtype=string_dtypes("pai_machine_spec"),
    )
    caps = dict(zip(spec["machine"], spec["cap_gpu"]))

    metric_path = DATA_DIR / "pai_machine_metric" / "pai_machine_metric.csv"
    valid = 0
    raw_gt_100 = 0
    normalized_gt_1 = 0
    normalized_gt_1_05 = 0
    ratio_sum = 0.0
    ratio_max = -np.inf
    unknown_machine = 0
    for chunk in pd.read_csv(
        metric_path, header=None, names=SCHEMAS["pai_machine_metric"],
        dtype=string_dtypes("pai_machine_metric"), chunksize=CHUNK_SIZE, low_memory=False,
    ):
        usable = chunk[["machine", "machine_gpu"]].dropna()
        caps_for_rows = usable["machine"].map(caps)
        unknown_machine += int(caps_for_rows.isna().sum())
        mask = caps_for_rows.notna() & (caps_for_rows > 0)
        raw = usable.loc[mask, "machine_gpu"]
        cap = caps_for_rows.loc[mask]
        ratio = raw / (100.0 * cap)
        valid += int(ratio.size)
        raw_gt_100 += int((raw > 100).sum())
        normalized_gt_1 += int((ratio > 1.0).sum())
        normalized_gt_1_05 += int((ratio > 1.05).sum())
        ratio_sum += float(ratio.sum())
        if ratio.size:
            ratio_max = max(ratio_max, float(ratio.max()))

    return {
        "valid_rows_with_gpu_capacity": valid,
        "unknown_machine_rows": unknown_machine,
        "raw_machine_gpu_gt_100": raw_gt_100,
        "normalized_gt_1": normalized_gt_1,
        "normalized_gt_1_05": normalized_gt_1_05,
        "normalized_mean": ratio_sum / valid if valid else None,
        "normalized_max": ratio_max if valid else None,
    }


def sensor_gpu_checks() -> dict[str, int | float]:
    path = DATA_DIR / "pai_sensor_table" / "pai_sensor_table.csv"
    rows = 0
    zero = 0
    gt_100 = 0
    gt_800 = 0
    maximum = 0.0
    for chunk in pd.read_csv(
        path, header=None, names=SCHEMAS["pai_sensor_table"],
        dtype=string_dtypes("pai_sensor_table"), chunksize=CHUNK_SIZE, low_memory=False,
    ):
        values = chunk["gpu_wrk_util"].dropna()
        rows += int(values.size)
        zero += int((values == 0).sum())
        gt_100 += int((values > 100).sum())
        gt_800 += int((values > 800).sum())
        if values.size:
            maximum = max(maximum, float(values.max()))
    return {"non_null_rows": rows, "zero": zero, "gt_100": gt_100, "gt_800": gt_800, "max": maximum}


def main() -> int:
    output = {
        "status_completeness": {
            table: status_completeness(table) for table in STATUS_FIELDS
        },
        "task_gpu_missing_matrix": task_missing_matrix(),
        "task_resource_quantiles": task_resource_quantiles(),
        "machine_gpu_normalization": machine_gpu_normalization(),
        "sensor_gpu_checks": sensor_gpu_checks(),
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False, indent=2))
    print(f"Wrote {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
