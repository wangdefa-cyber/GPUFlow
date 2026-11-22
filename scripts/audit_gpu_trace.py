"""Chunked audit of the Alibaba GPU cluster trace.

The source CSV files have no header row. Column names and checksums below are
taken from the official cluster-trace-gpu-v2020 README. The script never loads
an entire table into memory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_OUTPUT = PROJECT_ROOT / "reports" / "data_audit.json"
DEFAULT_SUMMARY = PROJECT_ROOT / "reports" / "data_profile_summary.csv"

TABLES: dict[str, dict[str, Any]] = {
    "pai_job_table": {
        "subdir": "pai_job_table",
        "columns": ["job_name", "inst_id", "user", "status", "start_time", "end_time"],
        "string_columns": ["job_name", "inst_id", "user", "status"],
        "checksum": "379ecb3becaba347f44a53bf7eb53e54b185221b2a0338a3f828828d269ba96c",
        "categorical": ["status"],
        "key_sets": {
            "job_name": ["job_name"],
            "inst_id": ["inst_id"],
            "job_name+inst_id": ["job_name", "inst_id"],
        },
        "time_pairs": [("start_time", "end_time")],
    },
    "pai_task_table": {
        "subdir": "pai_task_table",
        "columns": [
            "job_name", "task_name", "inst_num", "status", "start_time", "end_time",
            "plan_cpu", "plan_mem", "plan_gpu", "gpu_type",
        ],
        "string_columns": ["job_name", "task_name", "status", "gpu_type"],
        "checksum": "6954802b457305f8a9e480ef97c40060baee59649fd3adc62c5a1e048aa058de",
        "categorical": ["task_name", "status", "gpu_type"],
        "key_sets": {
            "job_name": ["job_name"],
            "job_name+task_name": ["job_name", "task_name"],
        },
        "time_pairs": [("start_time", "end_time")],
    },
    "pai_instance_table": {
        "subdir": "pai_instance_table",
        "columns": [
            "job_name", "task_name", "inst_name", "worker_name", "inst_id",
            "status", "start_time", "end_time", "machine",
        ],
        "string_columns": [
            "job_name", "task_name", "inst_name", "worker_name", "inst_id",
            "status", "machine",
        ],
        "checksum": "b179f7d7e0927a6663d719b728c92640447c5a0fc3c6e4edff31e7207ab9dd17",
        "categorical": ["task_name", "status"],
        "key_sets": {
            "worker_name": ["worker_name"],
            "inst_id": ["inst_id"],
            "machine": ["machine"],
            "job_name+task_name+inst_name": ["job_name", "task_name", "inst_name"],
        },
        "time_pairs": [("start_time", "end_time")],
    },
    "pai_sensor_table": {
        "subdir": "pai_sensor_table",
        "columns": [
            "job_name", "task_name", "worker_name", "inst_id", "machine",
            "gpu_name", "cpu_usage", "gpu_wrk_util", "avg_mem", "max_mem",
            "avg_gpu_wrk_mem", "max_gpu_wrk_mem", "read", "write", "read_count",
            "write_count",
        ],
        "string_columns": [
            "job_name", "task_name", "worker_name", "inst_id", "machine", "gpu_name",
        ],
        "checksum": "12dd9929b70f3efe18d1279d9873e3a519c64f431613b23b059ed8c46a376dd7",
        "categorical": ["task_name", "gpu_name"],
        "key_sets": {
            "worker_name": ["worker_name"],
            "inst_id": ["inst_id"],
            "machine": ["machine"],
            "worker_name+gpu_name": ["worker_name", "gpu_name"],
        },
        "time_pairs": [],
    },
    "pai_group_tag_table": {
        "subdir": "pai_group_tag_table",
        "columns": ["inst_id", "user", "gpu_type_spec", "group", "workload"],
        "string_columns": ["inst_id", "user", "gpu_type_spec", "group", "workload"],
        "checksum": "d23fcb56d88b2976fda4a62708d77b2a8c98635c4b443f100ed5553d4cd07fbe",
        "categorical": ["gpu_type_spec", "workload"],
        "key_sets": {
            "inst_id": ["inst_id"],
            "group": ["group"],
            "inst_id+group": ["inst_id", "group"],
        },
        "time_pairs": [],
    },
    "pai_machine_spec": {
        "subdir": "pai_machine_spec",
        "columns": ["machine", "gpu_type", "cap_cpu", "cap_mem", "cap_gpu"],
        "string_columns": ["machine", "gpu_type"],
        "checksum": "251e9e33649155a6a935fdc1dc0e90cd4698206936b60bd8fce60ff2ccd51439",
        "categorical": ["gpu_type"],
        "key_sets": {"machine": ["machine"]},
        "time_pairs": [],
    },
    "pai_machine_metric": {
        "subdir": "pai_machine_metric",
        "columns": [
            "worker_name", "machine", "start_time", "end_time",
            "machine_cpu_iowait", "machine_cpu_kernel", "machine_cpu_usr",
            "machine_gpu", "machine_load_1", "machine_net_receive",
            "machine_num_worker", "machine_cpu",
        ],
        "string_columns": ["worker_name", "machine"],
        "checksum": "8b6592daab0373ef7fec730198b4df5891b1722c2ab4c7016249166e131402d3",
        "categorical": [],
        "key_sets": {
            "worker_name": ["worker_name"],
            "machine": ["machine"],
            "worker_name+machine+start_time+end_time": [
                "worker_name", "machine", "start_time", "end_time"
            ],
        },
        "time_pairs": [("start_time", "end_time")],
    },
}


def sha256_file(path: Path, block_size: int = 8 * 1024 * 1024) -> str:
    """Return the SHA-256 digest for a file without loading it into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(block_size):
            digest.update(block)
    return digest.hexdigest()


def json_value(value: Any) -> Any:
    """Convert pandas/numpy scalar values to JSON-safe Python values."""
    if value is None:
        return None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if math.isnan(float(value)) else float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if pd.isna(value):
        return None
    return value


def hash_frame(frame: pd.DataFrame, columns: list[str]) -> np.ndarray:
    """Hash selected columns into a deterministic uint64 array."""
    return pd.util.hash_pandas_object(frame.loc[:, columns], index=False).to_numpy(
        dtype=np.uint64, copy=False
    )


def unique_stats(hash_chunks: list[np.ndarray]) -> dict[str, int]:
    """Count total/unique hash values and hash-level duplicates."""
    if not hash_chunks:
        return {"rows": 0, "unique": 0, "duplicates": 0}
    hashes = np.concatenate(hash_chunks)
    unique = np.unique(hashes)
    return {
        "rows": int(hashes.size),
        "unique": int(unique.size),
        "duplicates": int(hashes.size - unique.size),
    }


def audit_table(
    table_name: str,
    spec: dict[str, Any],
    data_dir: Path,
    chunksize: int,
    verify_checksum: bool,
) -> dict[str, Any]:
    """Audit one CSV table in bounded-memory chunks."""
    csv_path = data_dir / spec["subdir"] / f"{table_name}.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"Missing data file: {csv_path}")

    started = time.perf_counter()
    row_count = 0
    chunk_count = 0
    missing = Counter({column: 0 for column in spec["columns"]})
    categorical = {column: Counter() for column in spec["categorical"]}
    numeric: dict[str, dict[str, float | int]] = {}
    durations: dict[str, dict[str, float | int]] = {
        f"{start}->{end}": {
            "valid_pairs": 0,
            "negative": 0,
            "zero": 0,
            "min": math.inf,
            "max": -math.inf,
            "sum": 0.0,
        }
        for start, end in spec["time_pairs"]
    }
    row_hash_chunks: list[np.ndarray] = []
    key_hash_chunks: dict[str, list[np.ndarray]] = {
        key_name: [] for key_name in spec["key_sets"]
    }
    first_samples: list[dict[str, Any]] = []
    later_samples: list[dict[str, Any]] = []

    dtype_map = {
        column: "string" if column in spec["string_columns"] else "float64"
        for column in spec["columns"]
    }
    observed_dtypes: dict[str, str] = {}

    for chunk in pd.read_csv(
        csv_path,
        header=None,
        names=spec["columns"],
        dtype=dtype_map,
        chunksize=chunksize,
        low_memory=False,
    ):
        chunk_count += 1
        row_count += len(chunk)
        if not observed_dtypes:
            observed_dtypes = {key: str(value) for key, value in chunk.dtypes.items()}

        missing.update(chunk.isna().sum().astype(int).to_dict())

        for column, counter in categorical.items():
            values = chunk[column].fillna("<NULL>").astype(str)
            counter.update(values.value_counts().to_dict())

        for column in dtype_map:
            if dtype_map[column] != "float64":
                continue
            series = chunk[column]
            valid = series.dropna()
            profile = numeric.setdefault(
                column,
                {"non_null": 0, "min": math.inf, "max": -math.inf, "sum": 0.0,
                 "negative": 0, "zero": 0},
            )
            profile["non_null"] += int(valid.size)
            if valid.size:
                profile["min"] = min(float(profile["min"]), float(valid.min()))
                profile["max"] = max(float(profile["max"]), float(valid.max()))
                profile["sum"] += float(valid.sum())
                profile["negative"] += int((valid < 0).sum())
                profile["zero"] += int((valid == 0).sum())

        for start, end in spec["time_pairs"]:
            key = f"{start}->{end}"
            valid = chunk[[start, end]].dropna()
            duration = valid[end] - valid[start]
            profile = durations[key]
            profile["valid_pairs"] += int(duration.size)
            if duration.size:
                profile["negative"] += int((duration < 0).sum())
                profile["zero"] += int((duration == 0).sum())
                profile["min"] = min(float(profile["min"]), float(duration.min()))
                profile["max"] = max(float(profile["max"]), float(duration.max()))
                profile["sum"] += float(duration.sum())

        row_hash_chunks.append(hash_frame(chunk, spec["columns"]))
        for key_name, columns in spec["key_sets"].items():
            key_hash_chunks[key_name].append(hash_frame(chunk, columns))

        sample = chunk.head(3).to_dict(orient="records")
        if chunk_count == 1:
            first_samples = sample
        else:
            later_samples = sample[-2:]

    file_size = csv_path.stat().st_size
    checksum = sha256_file(csv_path) if verify_checksum else None
    row_hash_stats = unique_stats(row_hash_chunks)
    key_stats = {name: unique_stats(chunks) for name, chunks in key_hash_chunks.items()}

    fields = []
    for column in spec["columns"]:
        missing_count = int(missing[column])
        fields.append(
            {
                "name": column,
                "dtype": observed_dtypes.get(column),
                "missing": missing_count,
                "missing_pct": round(missing_count / row_count * 100, 6) if row_count else 0.0,
            }
        )

    numeric_output = {}
    for column, profile in numeric.items():
        non_null = int(profile["non_null"])
        numeric_output[column] = {
            "non_null": non_null,
            "min": None if non_null == 0 else float(profile["min"]),
            "max": None if non_null == 0 else float(profile["max"]),
            "mean": None if non_null == 0 else float(profile["sum"]) / non_null,
            "negative_values": int(profile["negative"]),
            "zero_values": int(profile["zero"]),
        }

    durations_output = {}
    for key, profile in durations.items():
        pairs = int(profile["valid_pairs"])
        durations_output[key] = {
            "valid_pairs": pairs,
            "negative_durations": int(profile["negative"]),
            "zero_durations": int(profile["zero"]),
            "min": None if pairs == 0 else float(profile["min"]),
            "max": None if pairs == 0 else float(profile["max"]),
            "mean": None if pairs == 0 else float(profile["sum"]) / pairs,
        }

    categorical_output = {
        column: dict(counter.most_common(50))
        for column, counter in categorical.items()
    }
    samples = first_samples + later_samples
    elapsed = time.perf_counter() - started
    return {
        "table": table_name,
        "path": str(csv_path.relative_to(PROJECT_ROOT)),
        "file_size_bytes": file_size,
        "file_size_mb": round(file_size / 1024 / 1024, 3),
        "sha256": checksum,
        "checksum_match": None if checksum is None else checksum == spec["checksum"],
        "rows": row_count,
        "columns": len(spec["columns"]),
        "chunks": chunk_count,
        "duplicate_rows_by_full_row_hash": row_hash_stats["duplicates"],
        "unique_rows_by_full_row_hash": row_hash_stats["unique"],
        "key_cardinality": {name: stats["unique"] for name, stats in key_stats.items()},
        "key_duplicate_rows": {name: stats["duplicates"] for name, stats in key_stats.items()},
        "fields": fields,
        "numeric_profile": numeric_output,
        "duration_profile": durations_output,
        "categorical_profile": categorical_output,
        "sample_rows": [
            {key: json_value(value) for key, value in row.items()} for row in samples
        ],
        "audit_seconds": round(elapsed, 2),
    }


def write_summary(results: list[dict[str, Any]], output: Path) -> None:
    """Write a compact CSV profile for quick review."""
    rows = []
    for result in results:
        rows.append(
            {
                "table": result["table"],
                "rows": result["rows"],
                "columns": result["columns"],
                "file_size_mb": result["file_size_mb"],
                "duplicate_rows": result["duplicate_rows_by_full_row_hash"],
                "missing_cells": sum(field["missing"] for field in result["fields"]),
                "checksum_match": result["checksum_match"],
                "audit_seconds": result["audit_seconds"],
            }
        )
    pd.DataFrame(rows).to_csv(output, index=False, encoding="utf-8-sig")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--chunksize", type=int, default=200_000)
    parser.add_argument("--skip-hash", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.summary.parent.mkdir(parents=True, exist_ok=True)

    results = []
    for table_name, spec in TABLES.items():
        print(f"Auditing {table_name} ...", flush=True)
        result = audit_table(
            table_name=table_name,
            spec=spec,
            data_dir=args.data_dir,
            chunksize=args.chunksize,
            verify_checksum=not args.skip_hash,
        )
        results.append(result)
        print(
            f"  rows={result['rows']:,} columns={result['columns']} "
            f"duplicates={result['duplicate_rows_by_full_row_hash']:,}",
            flush=True,
        )

    payload = {
        "dataset": "Alibaba cluster-trace-gpu-v2020",
        "official_readme": "docs/reference/alibaba_gpu_trace_readme.md",
        "method": (
            "CSV read in bounded-memory chunks. Duplicate and key-cardinality "
            "counts use pandas 64-bit row hashes; collisions are theoretically "
            "possible but negligible. SHA-256 is calculated by streaming."
        ),
        "chunksize": args.chunksize,
        "tables": results,
    }
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_summary(results, args.summary)
    print(f"Wrote {args.output}")
    print(f"Wrote {args.summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
