"""Session-scoped prototype state helpers."""

from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import uuid4

import pandas as pd
import streamlit as st

from gpu_sim.prototype.logic import defaults


SERVER_KEY = "prototype_servers"
TASK_KEY = "prototype_tasks"
SCHEDULER_KEY = "prototype_scheduler"
EDITOR_VERSION_KEY = "prototype_editor_version"


def initialize_state() -> None:
    """Initialize editable system configuration once per browser session."""
    if SERVER_KEY not in st.session_state:
        servers, tasks, scheduler = defaults()
        st.session_state[SERVER_KEY] = servers
        st.session_state[TASK_KEY] = tasks
        st.session_state[SCHEDULER_KEY] = scheduler
    if EDITOR_VERSION_KEY not in st.session_state:
        st.session_state[EDITOR_VERSION_KEY] = 1


def reset_state() -> None:
    """Reset prototype configuration without touching real historical data."""
    servers, tasks, scheduler = defaults()
    st.session_state[SERVER_KEY] = servers
    st.session_state[TASK_KEY] = tasks
    st.session_state[SCHEDULER_KEY] = scheduler
    st.session_state[EDITOR_VERSION_KEY] = int(st.session_state.get(EDITOR_VERSION_KEY, 1)) + 1


def get_servers() -> list[dict[str, Any]]:
    initialize_state()
    return deepcopy(st.session_state[SERVER_KEY])


def get_tasks() -> list[dict[str, Any]]:
    initialize_state()
    return deepcopy(st.session_state[TASK_KEY])


def get_scheduler() -> dict[str, Any]:
    initialize_state()
    return deepcopy(st.session_state[SCHEDULER_KEY])


def editor_version() -> int:
    initialize_state()
    return int(st.session_state[EDITOR_VERSION_KEY])


def servers_frame() -> pd.DataFrame:
    return pd.DataFrame(get_servers())


def tasks_frame() -> pd.DataFrame:
    rows = get_tasks()
    for index, row in enumerate(rows):
        row.setdefault("sequence", index)
    return pd.DataFrame(rows)


def save_servers(records: list[dict[str, Any]]) -> None:
    """Persist normalized editable server records in session state."""
    normalized: list[dict[str, Any]] = []
    for row in records:
        server_id = str(row.get("id") or "").strip() or f"srv-{uuid4().hex[:8]}"
        normalized.append(
            {
                "id": server_id,
                "name": str(row.get("name") or "").strip(),
                "gpu_type": str(row.get("gpu_type") or "P100").strip(),
                "gpu_capacity": float(row.get("gpu_capacity") or 0),
                "cpu_capacity": float(row.get("cpu_capacity") or 0),
                "memory_capacity_gb": float(row.get("memory_capacity_gb") or 0),
                "status": str(row.get("status") or "Active").strip(),
            }
        )
    st.session_state[SERVER_KEY] = normalized


def save_tasks(records: list[dict[str, Any]]) -> None:
    """Persist normalized editable task records in session state."""
    normalized: list[dict[str, Any]] = []
    for index, row in enumerate(records):
        task_id = str(row.get("id") or "").strip() or f"task-{uuid4().hex[:8]}"
        normalized.append(
            {
                "id": task_id,
                "name": str(row.get("name") or "").strip(),
                "source_type": "USER_CREATED",
                "gpu_required": float(row.get("gpu_required") or 0),
                "cpu_required": float(row.get("cpu_required") or 0),
                "memory_required_gb": float(row.get("memory_required_gb") or 0),
                "priority": int(row.get("priority") or 0),
                "estimated_duration": float(row.get("estimated_duration") or 0),
                "gpu_type_required": str(row.get("gpu_type_required") or "").strip(),
                "submit_time": float(row.get("submit_time") or 0),
                "sequence": index,
            }
        )
    st.session_state[TASK_KEY] = normalized


def save_scheduler(config: dict[str, Any]) -> None:
    st.session_state[SCHEDULER_KEY] = {
        "preset": str(config.get("preset") or "FIFO"),
        "wait_sla_seconds": int(config.get("wait_sla_seconds") or 0),
        "random_seed": int(config.get("random_seed") or 0),
        "allow_skip_head": bool(config.get("allow_skip_head", False)),
    }
