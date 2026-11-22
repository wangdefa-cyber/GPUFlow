"""Pure prototype rules shared by the Streamlit pages and tests."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from math import isfinite
from typing import Any


GPU_TYPES: tuple[str, ...] = ("P100", "T4", "V100", "V100M32", "MISC")
SERVER_STATUSES: tuple[str, ...] = ("Active", "Draining", "Disabled")

PRESETS: dict[str, dict[str, str]] = {
    "FIFO": {
        "label": "FIFO",
        "order_rule": "FIFO",
        "placement_rule": "First Fit",
        "description": "按到达时间与任务序号排序，再选择第一个满足全部资源约束的服务器。",
    },
    "SJF": {
        "label": "SJF",
        "order_rule": "SJF",
        "placement_rule": "First Fit",
        "description": "优先选择预计运行时长较短的任务，降低平均等待时间。",
    },
    "Priority": {
        "label": "Priority",
        "order_rule": "Priority",
        "placement_rule": "First Fit",
        "description": "高优先级任务先调度，同优先级按到达时间排序。",
    },
    "Best Fit": {
        "label": "Best Fit",
        "order_rule": "FIFO",
        "placement_rule": "Best Fit",
        "description": "保持 FIFO 排序，选择放置后剩余资源比例最小的服务器。",
    },
}

DEFAULT_SERVERS: list[dict[str, Any]] = [
    {
        "id": "srv-001",
        "name": "P100-01",
        "gpu_type": "P100",
        "gpu_capacity": 2.0,
        "cpu_capacity": 64.0,
        "memory_capacity_gb": 512.0,
        "status": "Active",
    },
    {
        "id": "srv-002",
        "name": "P100-02",
        "gpu_type": "P100",
        "gpu_capacity": 2.0,
        "cpu_capacity": 64.0,
        "memory_capacity_gb": 512.0,
        "status": "Active",
    },
    {
        "id": "srv-003",
        "name": "T4-01",
        "gpu_type": "T4",
        "gpu_capacity": 2.0,
        "cpu_capacity": 96.0,
        "memory_capacity_gb": 512.0,
        "status": "Active",
    },
    {
        "id": "srv-004",
        "name": "T4-02",
        "gpu_type": "T4",
        "gpu_capacity": 2.0,
        "cpu_capacity": 96.0,
        "memory_capacity_gb": 512.0,
        "status": "Active",
    },
    {
        "id": "srv-005",
        "name": "V100-01",
        "gpu_type": "V100",
        "gpu_capacity": 8.0,
        "cpu_capacity": 96.0,
        "memory_capacity_gb": 512.0,
        "status": "Active",
    },
    {
        "id": "srv-006",
        "name": "V100M32-01",
        "gpu_type": "V100M32",
        "gpu_capacity": 8.0,
        "cpu_capacity": 96.0,
        "memory_capacity_gb": 384.0,
        "status": "Active",
    },
    {
        "id": "srv-007",
        "name": "MISC-01",
        "gpu_type": "MISC",
        "gpu_capacity": 8.0,
        "cpu_capacity": 96.0,
        "memory_capacity_gb": 512.0,
        "status": "Active",
    },
]

DEFAULT_TASKS: list[dict[str, Any]] = [
    {
        "id": "task-001",
        "name": "BERT 训练 A",
        "source_type": "USER_CREATED",
        "gpu_required": 4.0,
        "cpu_required": 24.0,
        "memory_required_gb": 64.0,
        "priority": 8,
        "estimated_duration": 3600.0,
        "gpu_type_required": "V100",
        "submit_time": 0.0,
    },
    {
        "id": "task-002",
        "name": "图像推理批次",
        "source_type": "USER_CREATED",
        "gpu_required": 1.0,
        "cpu_required": 8.0,
        "memory_required_gb": 16.0,
        "priority": 5,
        "estimated_duration": 900.0,
        "gpu_type_required": "T4",
        "submit_time": 120.0,
    },
    {
        "id": "task-003",
        "name": "特征工程实验",
        "source_type": "USER_CREATED",
        "gpu_required": 2.0,
        "cpu_required": 12.0,
        "memory_required_gb": 32.0,
        "priority": 6,
        "estimated_duration": 1800.0,
        "gpu_type_required": "V100M32",
        "submit_time": 240.0,
    },
    {
        "id": "task-004",
        "name": "CTR 预估训练",
        "source_type": "USER_CREATED",
        "gpu_required": 2.0,
        "cpu_required": 16.0,
        "memory_required_gb": 48.0,
        "priority": 9,
        "estimated_duration": 5400.0,
        "gpu_type_required": "P100",
        "submit_time": 300.0,
    },
    {
        "id": "task-005",
        "name": "NMT 调参",
        "source_type": "USER_CREATED",
        "gpu_required": 1.0,
        "cpu_required": 4.0,
        "memory_required_gb": 12.0,
        "priority": 4,
        "estimated_duration": 600.0,
        "gpu_type_required": "MISC",
        "submit_time": 420.0,
    },
    {
        "id": "task-006",
        "name": "GraphLearn 预训练",
        "source_type": "USER_CREATED",
        "gpu_required": 8.0,
        "cpu_required": 32.0,
        "memory_required_gb": 96.0,
        "priority": 7,
        "estimated_duration": 7200.0,
        "gpu_type_required": "V100",
        "submit_time": 600.0,
    },
]

DEFAULT_SCHEDULER: dict[str, Any] = {
    "preset": "FIFO",
    "wait_sla_seconds": 900,
    "random_seed": 20261122,
    "allow_skip_head": False,
}


@dataclass(frozen=True)
class CapacitySummary:
    server_count: int
    active_server_count: int
    total_gpu: float
    total_cpu: float
    total_memory_gb: float


def defaults() -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Return deep copies so session state never mutates module constants."""
    return deepcopy(DEFAULT_SERVERS), deepcopy(DEFAULT_TASKS), deepcopy(DEFAULT_SCHEDULER)


def validate_servers(records: list[dict[str, Any]]) -> list[str]:
    """Validate editable prototype server rows and return user-facing errors."""
    errors: list[str] = []
    names: set[str] = set()
    if not records:
        return ["至少需要一台虚拟 GPU 服务器。"]

    for index, row in enumerate(records, start=1):
        name = str(row.get("name") or "").strip()
        gpu_type = str(row.get("gpu_type") or "").strip()
        status = str(row.get("status") or "Active").strip()
        if not name:
            errors.append(f"第 {index} 台服务器缺少名称。")
        elif name in names:
            errors.append(f"服务器名称重复：{name}。")
        names.add(name)

        if gpu_type not in GPU_TYPES:
            errors.append(f"服务器 {name or index} 的 GPU 型号无效。")
        if status not in SERVER_STATUSES:
            errors.append(f"服务器 {name or index} 的状态无效。")

        for field, label in (
            ("gpu_capacity", "GPU 容量"),
            ("cpu_capacity", "CPU 容量"),
            ("memory_capacity_gb", "内存容量"),
        ):
            value = row.get(field)
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                errors.append(f"服务器 {name or index} 的{label}必须是数字。")
                continue
            if not isfinite(numeric):
                errors.append(f"服务器 {name or index} 的{label}必须是有限数字。")
            elif numeric < 0:
                errors.append(f"服务器 {name or index} 的{label}不能为负数。")
        try:
            if float(row.get("gpu_capacity")) <= 0:
                errors.append(f"服务器 {name or index} 的 GPU 容量必须大于 0。")
        except (TypeError, ValueError):
            pass
    return errors


def validate_tasks(records: list[dict[str, Any]]) -> list[str]:
    """Validate editable prototype task rows and return user-facing errors."""
    errors: list[str] = []
    names: set[str] = set()
    if not records:
        return ["至少需要一条仿真任务。"]

    for index, row in enumerate(records, start=1):
        name = str(row.get("name") or "").strip()
        gpu_type = str(row.get("gpu_type_required") or "").strip()
        if not name:
            errors.append(f"第 {index} 条任务缺少名称。")
        elif name in names:
            errors.append(f"任务名称重复：{name}。")
        names.add(name)

        if gpu_type and gpu_type not in GPU_TYPES:
            errors.append(f"任务 {name or index} 的 GPU 型号要求无效。")

        for field, label in (
            ("gpu_required", "GPU 需求"),
            ("cpu_required", "CPU 需求"),
            ("memory_required_gb", "内存需求"),
            ("submit_time", "到达时间"),
        ):
            try:
                numeric = float(row.get(field))
            except (TypeError, ValueError):
                errors.append(f"任务 {name or index} 的{label}必须是数字。")
                continue
            if not isfinite(numeric):
                errors.append(f"任务 {name or index} 的{label}必须是有限数字。")
            elif numeric < 0:
                errors.append(f"任务 {name or index} 的{label}不能为负数。")

        try:
            if float(row.get("estimated_duration")) <= 0:
                errors.append(f"任务 {name or index} 的预计运行时长必须大于 0。")
        except (TypeError, ValueError):
            errors.append(f"任务 {name or index} 的预计运行时长必须是数字。")

        try:
            priority = int(row.get("priority"))
            if priority < 0 or priority > 100:
                errors.append(f"任务 {name or index} 的优先级必须在 0–100。")
        except (TypeError, ValueError):
            errors.append(f"任务 {name or index} 的优先级必须是整数。")

        try:
            demand_total = (
                float(row.get("gpu_required"))
                + float(row.get("cpu_required"))
                + float(row.get("memory_required_gb"))
            )
            if demand_total <= 0:
                errors.append(f"任务 {name or index} 至少需要一种资源。")
        except (TypeError, ValueError):
            pass
    return errors


def capacity_summary(servers: list[dict[str, Any]]) -> CapacitySummary:
    """Aggregate configured capacity without implying any task is running."""
    active = [row for row in servers if str(row.get("status", "Active")) == "Active"]
    return CapacitySummary(
        server_count=len(servers),
        active_server_count=len(active),
        total_gpu=sum(float(row.get("gpu_capacity", 0) or 0) for row in active),
        total_cpu=sum(float(row.get("cpu_capacity", 0) or 0) for row in active),
        total_memory_gb=sum(
            float(row.get("memory_capacity_gb", 0) or 0) for row in active
        ),
    )


def order_tasks(
    tasks: list[dict[str, Any]], preset: str
) -> list[dict[str, Any]]:
    """Return a deterministic ordering preview for the selected scheduler preset."""
    config = PRESETS.get(preset, PRESETS["FIFO"])
    rule = config["order_rule"]

    def seq(row: dict[str, Any]) -> int:
        return int(row.get("sequence", 0) or 0)

    if rule == "SJF":
        return sorted(
            tasks,
            key=lambda row: (
                float(row.get("estimated_duration", 0) or 0),
                float(row.get("submit_time", 0) or 0),
                seq(row),
                str(row.get("name", "")),
            ),
        )
    if rule == "Priority":
        return sorted(
            tasks,
            key=lambda row: (
                -int(row.get("priority", 0) or 0),
                float(row.get("submit_time", 0) or 0),
                seq(row),
                str(row.get("name", "")),
            ),
        )
    return sorted(
        tasks,
        key=lambda row: (
            float(row.get("submit_time", 0) or 0),
            seq(row),
            str(row.get("name", "")),
        ),
    )


def server_can_fit(server: dict[str, Any], task: dict[str, Any]) -> bool:
    """Check whether one task fits one server under all resource constraints."""
    if str(server.get("status", "Active")) != "Active":
        return False
    required_type = str(task.get("gpu_type_required") or "").strip()
    if required_type and required_type != str(server.get("gpu_type", "")):
        return False
    return (
        float(task.get("gpu_required", 0) or 0)
        <= float(server.get("gpu_capacity", 0) or 0)
        and float(task.get("cpu_required", 0) or 0)
        <= float(server.get("cpu_capacity", 0) or 0)
        and float(task.get("memory_required_gb", 0) or 0)
        <= float(server.get("memory_capacity_gb", 0) or 0)
    )


def preflight_tasks(
    tasks: list[dict[str, Any]], servers: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Perform a static capacity check, not a dynamic scheduling simulation."""
    rows: list[dict[str, Any]] = []
    for task in order_tasks(tasks, "FIFO"):
        candidates = [server for server in servers if server_can_fit(server, task)]
        if candidates:
            status = "可容纳"
            reason = f"{len(candidates)} 台服务器满足全部约束"
        else:
            matching_type = [
                server
                for server in servers
                if not str(task.get("gpu_type_required") or "").strip()
                or str(server.get("gpu_type")) == str(task.get("gpu_type_required"))
            ]
            if matching_type:
                status = "容量不足"
                reason = "有同型号服务器，但 GPU/CPU/内存至少一项不足"
            else:
                status = "型号不匹配"
                reason = "当前配置中没有满足 GPU 型号要求的服务器"
        rows.append(
            {
                "任务": task.get("name", ""),
                "GPU 需求": float(task.get("gpu_required", 0) or 0),
                "CPU 需求": float(task.get("cpu_required", 0) or 0),
                "内存需求 GB": float(task.get("memory_required_gb", 0) or 0),
                "GPU 型号": task.get("gpu_type_required") or "任意",
                "预检结果": status,
                "原因": reason,
            }
        )
    return rows


def simulation_readiness(
    servers: list[dict[str, Any]],
    tasks: list[dict[str, Any]],
    scheduler: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return stage-gate checks for the prototype, without claiming a run exists."""
    server_errors = validate_servers(servers)
    task_errors = validate_tasks(tasks)
    summary = capacity_summary(servers)
    preflight = preflight_tasks(tasks, servers)
    all_fit = all(row["预检结果"] == "可容纳" for row in preflight)
    return [
        {
            "检查项": "集群配置",
            "状态": "通过" if not server_errors else "未通过",
            "说明": "服务器容量与型号合法" if not server_errors else server_errors[0],
        },
        {
            "检查项": "任务定义",
            "状态": "通过" if not task_errors else "未通过",
            "说明": "任务资源与时长合法" if not task_errors else task_errors[0],
        },
        {
            "检查项": "GPU 容量",
            "状态": "通过" if summary.total_gpu > 0 else "未通过",
            "说明": f"当前活动集群合计 {summary.total_gpu:g} GPU 当量",
        },
        {
            "检查项": "静态容量预检",
            "状态": "通过" if all_fit else "警告",
            "说明": "全部任务均可由至少一台服务器容纳" if all_fit else "部分任务当前无可用服务器",
        },
        {
            "检查项": "调度配置",
            "状态": "通过" if scheduler.get("preset") in PRESETS else "未通过",
            "说明": f"当前预设：{scheduler.get('preset', '未配置')}",
        },
        {
            "检查项": "仿真引擎",
            "状态": "阶段 4",
            "说明": "离散事件引擎尚未实现，本页仅验证原型输入",
        },
    ]
