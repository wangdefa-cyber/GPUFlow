"""Stable compatibility keys for comparing simulation runs."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def run_compatibility_key(run: Any) -> str:
    payload = {
        "tasks": run.task_snapshot_json,
        "servers": run.server_snapshot_json,
        "seed": run.random_seed,
        "sla": run.wait_sla_seconds,
        "skip": run.allow_skip_head,
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
