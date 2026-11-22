"""Deterministic discrete-event simulation engine for stage 4."""

from __future__ import annotations

import hashlib
import heapq
import json
from collections import defaultdict
from dataclasses import dataclass
from statistics import mean
from typing import Any

from gpu_sim.domain import (
    ResourceSample,
    ResourceVector,
    SchedulerSpec,
    ServerSpec,
    SimulationEvent,
    SimulationResult,
    TaskExecution,
    TaskSpec,
)
from gpu_sim.scheduling import choose_server, order_tasks


@dataclass(frozen=True)
class EngineInput:
    run_id: str
    tasks: list[TaskSpec]
    servers: list[ServerSpec]
    scheduler: SchedulerSpec


class SimulationEngine:
    """Run a deterministic event-driven scheduling experiment in memory."""

    def __init__(self, engine_input: EngineInput) -> None:
        if not engine_input.tasks:
            raise ValueError("Simulation requires at least one task")
        if not engine_input.servers:
            raise ValueError("Simulation requires at least one server")
        if len({task.id for task in engine_input.tasks}) != len(engine_input.tasks):
            raise ValueError("Task IDs must be unique")
        if len({server.id for server in engine_input.servers}) != len(engine_input.servers):
            raise ValueError("Server IDs must be unique")

        self.input = engine_input
        self.tasks = sorted(
            engine_input.tasks,
            key=lambda task: (task.submit_time, task.sequence_no, task.id),
        )
        self.servers = [
            server for server in engine_input.servers if server.status == "Active"
        ]
        if not self.servers:
            raise ValueError("Simulation requires at least one active server")

        self.allocations: dict[str, ResourceVector] = {
            server.id: ResourceVector() for server in self.servers
        }
        self.executions: dict[str, TaskExecution] = {
            task.id: TaskExecution(task=task) for task in self.tasks
        }
        self.waiting: list[str] = []
        self.events: list[SimulationEvent] = []
        self.samples_by_time: dict[float, ResourceSample] = {}
        self.heap: list[tuple[float, int, int, str, str | None]] = []
        self._heap_order = 0
        self._event_sequence = 0

    @property
    def total_capacity(self) -> ResourceVector:
        total = ResourceVector()
        for server in self.servers:
            total = total + server.capacity
        return total

    def _next_heap_order(self) -> int:
        self._heap_order += 1
        return self._heap_order

    def _record_event(
        self,
        event_time: float,
        event_type: str,
        task: TaskExecution | None = None,
        server_id: str | None = None,
        message: str = "",
        payload: dict[str, Any] | None = None,
    ) -> None:
        self._event_sequence += 1
        self.events.append(
            SimulationEvent(
                sequence_no=self._event_sequence,
                event_time=event_time,
                event_type=event_type,
                task_id=task.task.id if task else None,
                server_id=server_id,
                message=message,
                payload=payload or {},
            )
        )

    def _push_arrival(self, task: TaskExecution) -> None:
        heapq.heappush(
            self.heap,
            (task.task.submit_time, 1, self._next_heap_order(), "ARRIVAL", task.task.id),
        )

    def _push_completion(self, execution: TaskExecution, finish_time: float) -> None:
        heapq.heappush(
            self.heap,
            (
                finish_time,
                0,
                self._next_heap_order(),
                "COMPLETION",
                execution.task.id,
            ),
        )

    def _allocate(self, execution: TaskExecution, server: ServerSpec, now: float) -> None:
        self.allocations[server.id] = (
            self.allocations[server.id] + execution.task.demand
        )
        execution.status = "RUNNING"
        execution.server_id = server.id
        execution.scheduled_time = now
        execution.start_time = now
        execution.wait_time = max(0.0, now - execution.task.submit_time)
        finish_time = now + execution.task.estimated_duration
        self._record_event(
            now,
            "TASK_SCHEDULED",
            execution,
            server.id,
            "task allocated to server",
            {"finish_time": finish_time},
        )
        self._record_event(
            now,
            "TASK_STARTED",
            execution,
            server.id,
            "task execution started",
        )
        self._push_completion(execution, finish_time)

    def _schedule_waiting(self, now: float) -> int:
        scheduled = 0
        while self.waiting:
            ordered_ids = [
                task.id
                for task in order_tasks(
                    [self.executions[task_id].task for task_id in self.waiting],
                    self.input.scheduler.order_rule,
                )
            ]
            if not ordered_ids:
                break

            candidate_ids = ordered_ids if self.input.scheduler.allow_skip_head else ordered_ids[:1]
            placed = False
            for task_id in candidate_ids:
                execution = self.executions[task_id]
                choice = choose_server(
                    execution.task,
                    self.servers,
                    self.allocations,
                    self.input.scheduler.placement_rule,
                    self.input.scheduler.weights,
                )
                if choice.server is None:
                    continue
                self.waiting.remove(task_id)
                self._allocate(execution, choice.server, now)
                scheduled += 1
                placed = True
                break
            if not placed:
                break
        return scheduled

    def _record_sample(self, now: float) -> None:
        gpu = sum((value.gpu for value in self.allocations.values()), start=0.0)
        cpu = sum((value.cpu for value in self.allocations.values()), start=0.0)
        memory = sum(
            (value.memory_gb for value in self.allocations.values()), start=0.0
        )
        capacity = self.total_capacity
        self.samples_by_time[round(now, 9)] = ResourceSample(
            simulation_time=now,
            gpu_allocated=gpu,
            cpu_allocated=cpu,
            memory_allocated_gb=memory,
            gpu_capacity=capacity.gpu,
            cpu_capacity=capacity.cpu,
            memory_capacity_gb=capacity.memory_gb,
        )

    def _finish_blocked(self, now: float) -> None:
        for task_id in list(self.waiting):
            execution = self.executions[task_id]
            execution.status = "BLOCKED"
            execution.wait_time = max(0.0, now - execution.task.submit_time)
            execution.timed_out = (
                execution.wait_time > self.input.scheduler.wait_sla_seconds
            )
            self._record_event(
                now,
                "TASK_BLOCKED",
                execution,
                None,
                "no future event can release enough capacity",
                {"wait_time": execution.wait_time},
            )
        self.waiting.clear()

    def _metrics(
        self, makespan: float | None, samples: list[ResourceSample]
    ) -> dict[str, float | None]:
        completed = [
            execution
            for execution in self.executions.values()
            if execution.status == "COMPLETED"
        ]
        total = len(self.executions)
        average_wait = (
            mean(execution.wait_time or 0.0 for execution in completed)
            if completed
            else None
        )
        average_turnaround = (
            mean(execution.turnaround_time or 0.0 for execution in completed)
            if completed
            else None
        )

        gpu_util = cpu_util = memory_util = None
        if makespan and makespan > 0 and samples:
            sorted_samples = sorted(samples, key=lambda sample: sample.simulation_time)
            gpu_energy = cpu_energy = memory_energy = 0.0
            for current, following in zip(sorted_samples, sorted_samples[1:]):
                delta = following.simulation_time - current.simulation_time
                if delta <= 0:
                    continue
                gpu_energy += current.gpu_allocated * delta
                cpu_energy += current.cpu_allocated * delta
                memory_energy += current.memory_allocated_gb * delta
            capacity = self.total_capacity
            if capacity.gpu > 0:
                gpu_util = gpu_energy / (capacity.gpu * makespan)
            if capacity.cpu > 0:
                cpu_util = cpu_energy / (capacity.cpu * makespan)
            if capacity.memory_gb > 0:
                memory_util = memory_energy / (capacity.memory_gb * makespan)

        timeout_count = sum(
            1 for execution in self.executions.values() if execution.timed_out
        )
        fairness = self._fairness_index(completed)
        return {
            "average_wait_seconds": average_wait,
            "average_turnaround_seconds": average_turnaround,
            "makespan_seconds": makespan,
            "gpu_utilization": gpu_util,
            "cpu_utilization": cpu_util,
            "memory_utilization": memory_util,
            "completion_rate": len(completed) / total if total else None,
            "timeout_rate": timeout_count / total if total else None,
            "fairness_index": fairness,
            "completed_tasks": float(len(completed)),
            "blocked_tasks": float(
                sum(
                    1
                    for execution in self.executions.values()
                    if execution.status == "BLOCKED"
                )
            ),
        }

    def _fairness_index(self, completed: list[TaskExecution]) -> float | None:
        allocations: dict[str, float] = defaultdict(float)
        for execution in completed:
            duration = (execution.end_time or 0.0) - (execution.start_time or 0.0)
            allocations[execution.task.user_key or "UNKNOWN"] += (
                execution.task.demand.gpu * duration
            )
        values = list(allocations.values())
        if not values or sum(values) <= 0:
            return None
        numerator = sum(values) ** 2
        denominator = len(values) * sum(value**2 for value in values)
        return numerator / denominator if denominator else None

    def run(self) -> SimulationResult:
        for execution in self.tasks:
            self._push_arrival(self.executions[execution.id])

        guard = 0
        while self.heap:
            guard += 1
            if guard > 1_000_000:
                raise RuntimeError("Simulation exceeded the event processing guard")

            now = self.heap[0][0]
            same_time: list[tuple[float, int, int, str, str | None]] = []
            while self.heap and self.heap[0][0] == now:
                same_time.append(heapq.heappop(self.heap))

            for _, _, _, event_type, task_id in same_time:
                if task_id is None:
                    continue
                execution = self.executions[task_id]
                if event_type == "COMPLETION":
                    server_id = execution.server_id
                    if server_id:
                        self.allocations[server_id] = (
                            self.allocations[server_id] - execution.task.demand
                        )
                    execution.end_time = now
                    execution.status = "COMPLETED"
                    execution.turnaround_time = (
                        execution.end_time - execution.task.submit_time
                    )
                    execution.timed_out = (
                        execution.wait_time or 0.0
                    ) > self.input.scheduler.wait_sla_seconds
                    self._record_event(
                        now,
                        "TASK_COMPLETED",
                        execution,
                        server_id,
                        "task completed and resources released",
                    )
                elif event_type == "ARRIVAL":
                    execution.status = "WAITING"
                    self.waiting.append(task_id)
                    self._record_event(
                        now,
                        "TASK_ARRIVED",
                        execution,
                        None,
                        "task entered the waiting queue",
                    )

            self._schedule_waiting(now)
            self._record_sample(now)

            if not self.heap and self.waiting:
                self._finish_blocked(now)
                self._record_sample(now)
                break

        completed = [
            execution for execution in self.executions.values() if execution.end_time is not None
        ]
        makespan = None
        if completed:
            start = min(execution.task.submit_time for execution in self.executions.values())
            makespan = max(execution.end_time or 0.0 for execution in completed) - start

        samples = sorted(self.samples_by_time.values(), key=lambda sample: sample.simulation_time)
        metrics = self._metrics(makespan, samples)
        self._record_event(
            samples[-1].simulation_time if samples else 0.0,
            "RUN_COMPLETED",
            None,
            None,
            "simulation event loop finished",
            {"makespan_seconds": makespan},
        )

        result_hash = self._result_hash()
        return SimulationResult(
            run_id=self.input.run_id,
            tasks=list(self.executions.values()),
            events=self.events,
            samples=samples,
            metrics=metrics,
            makespan=makespan,
            result_hash=result_hash,
            config=self.input.scheduler,
        )

    def _result_hash(self) -> str:
        payload = {
            "tasks": [task.as_dict() for task in self.tasks],
            "servers": [server.as_dict() for server in self.servers],
            "scheduler": self.input.scheduler.as_dict(),
            "events": [event.as_dict() for event in self.events],
        }
        encoded = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()
