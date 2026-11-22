# 阶段 2：模块接口设计

本文定义模块之间可依赖的窄契约。代码实现时应优先遵循这些业务接口，而不是把内部表结构泄露给其他模块。

## 1. 接口设计规则

1. 一个接口只暴露调用方真正需要的能力。
2. 请求和响应使用用例专用结构，不直接返回 ORM 对象。
3. 命令返回结果或业务错误；查询返回只读投影。
4. 仿真引擎不依赖 Streamlit。
5. 页面不直接访问数据库。
6. 外部时间、随机数和 ID 生成可注入，便于确定性测试。
7. 模块之间不允许通过修改对方的表来实现协作。
8. 所有修改操作必须带幂等键或输入哈希，避免重复启动实验。

## 2. 共享值对象

共享内容限制在真正稳定、跨模块一致的业务概念。

```python
from dataclasses import dataclass
from enum import StrEnum
from typing import Generic, Protocol, TypeVar


T = TypeVar("T")


class DataOrigin(StrEnum):
    HISTORICAL = "HISTORICAL"
    SYSTEM_CONFIG = "SYSTEM_CONFIG"
    SIMULATION = "SIMULATION"


@dataclass(frozen=True)
class ResourceVector:
    gpu_equivalent: float
    cpu_cores: float
    memory_gb: float

    def is_non_negative(self) -> bool: ...

    def fits_within(self, other: "ResourceVector") -> bool: ...

    def __add__(self, other: "ResourceVector") -> "ResourceVector": ...

    def __sub__(self, other: "ResourceVector") -> "ResourceVector": ...


@dataclass(frozen=True)
class TaskDemand:
    resources: ResourceVector
    gpu_type: str | None


@dataclass(frozen=True)
class Interval:
    start_second: float
    end_second: float
```

不变量：

- 所有数值有限且非负。
- `end_second >= start_second`。
- GPU 型号比较区分大小写按配置标准化；内部统一使用规范值。

## 3. 业务错误

```python
class GPUFlowError(Exception):
    code: str
    message: str


class ValidationError(GPUFlowError):
    code = "VALIDATION_ERROR"


class NotFoundError(GPUFlowError):
    code = "NOT_FOUND"


class ConflictError(GPUFlowError):
    code = "CONFLICT"


class CapacityViolationError(GPUFlowError):
    code = "CAPACITY_VIOLATION"


class InvalidTransitionError(GPUFlowError):
    code = "INVALID_TRANSITION"


class UnschedulableTaskError(GPUFlowError):
    code = "UNSCHEDULABLE_TASK"
```

错误响应必须包含：

- 稳定错误码。
- 用户可读原因。
- 受影响的资源、任务、配置或版本 ID。
- 可执行修正建议（适用时）。

## 4. 历史数据目录

```python
@dataclass(frozen=True)
class ImportDatasetRequest:
    data_dir: str
    dataset_name: str
    import_mode: str  # FULL | SAMPLED
    sampling_rule: dict | None
    random_seed: int | None
    idempotency_key: str


@dataclass(frozen=True)
class ImportDatasetResult:
    dataset_version_id: str
    status: str
    table_reports: tuple["TableImportReport", ...]
    quality_summary: dict
    activated: bool


@dataclass(frozen=True)
class HistoryQuery:
    dataset_version_id: str
    entity: str  # JOB | TASK | INSTANCE | SENSOR | MACHINE
    filters: dict
    page: int
    page_size: int


@dataclass(frozen=True)
class Page(Generic[T]):
    items: tuple[T, ...]
    total: int
    page: int
    page_size: int


class HistoricalDataCatalog(Protocol):
    def import_dataset(self, request: ImportDatasetRequest) -> ImportDatasetResult:
        """校验并导入七张表；全部成功后才允许激活。"""

    def query_history(self, query: HistoryQuery) -> Page[dict]:
        """返回带数据集版本和来源标记的只读投影。"""

    def get_quality_report(self, dataset_version_id: str) -> dict:
        """返回行数、缺失、状态、键覆盖和校验和结果。"""

    def build_workload_candidates(
        self,
        dataset_version_id: str,
        filters: dict,
    ) -> "WorkloadCandidateResult":
        """只返回可追溯候选，不直接创建实验。"""
```

### 4.1 不变量

- 原始文件不得被修改。
- 激活的数据集版本不可原地重导。
- 任何历史查询必须绑定 `dataset_version_id`。
- 导入错误不得通过返回空表掩盖。

## 5. 集群配置

```python
@dataclass(frozen=True)
class ServerDraft:
    name: str
    gpu_type: str
    gpu_capacity: float
    cpu_capacity: float
    memory_capacity_gb: float
    status: str
    template_machine: str | None


@dataclass(frozen=True)
class CreateClusterRequest:
    name: str
    servers: tuple[ServerDraft, ...]
    source_dataset_version_id: str | None


@dataclass(frozen=True)
class PublishClusterRequest:
    cluster_config_id: str
    expected_version_no: int


class ClusterConfigService(Protocol):
    def create_cluster(self, request: CreateClusterRequest) -> str:
        """创建 DRAFT 集群配置并校验名称与容量。"""

    def update_server(
        self,
        cluster_config_id: str,
        server_id: str,
        draft: ServerDraft,
        expected_version_no: int,
    ) -> None:
        """仅在预期版本匹配时修改 DRAFT 配置。"""

    def publish_cluster(self, request: PublishClusterRequest) -> str:
        """冻结配置并返回不可变版本 ID。"""

    def get_cluster_snapshot(self, cluster_config_id: str) -> "ClusterSnapshot":
        """返回实验可使用的只读容量快照。"""

    def validate_capacity(self, cluster_config_id: str) -> "CapacityReport":
        """检查资源、型号、服务器状态和重复名称。"""
```

### 5.1 不变量

- 任何服务器分配量不超过容量。
- PUBLISHED 配置不可编辑。
- 已引用配置不可删除。
- 服务器 ID 在配置版本内稳定。

## 6. 工作负载准备

```python
@dataclass(frozen=True)
class UserTaskDraft:
    name: str
    submit_time: float
    priority: int
    estimated_duration: float
    gpu_required: float
    cpu_required: float
    memory_required_gb: float
    gpu_type_required: str | None
    deadline_time: float | None
    wait_sla_seconds: int | None


@dataclass(frozen=True)
class BuildHistoricalWorkloadRequest:
    dataset_version_id: str
    name: str
    filters: dict
    sampling_mode: str
    sampling_rule: dict
    random_seed: int
    expand_tasks_without_instances: bool


class WorkloadService(Protocol):
    def create_task(self, workload_set_id: str, draft: UserTaskDraft) -> str:
        """向 DRAFT 工作负载集加入用户任务。"""

    def build_from_history(
        self, request: BuildHistoricalWorkloadRequest
    ) -> "WorkloadBuildResult":
        """把历史记录映射为可追溯的仿真任务。"""

    def freeze_workload(self, workload_set_id: str) -> str:
        """冻结任务集并返回输入哈希。"""

    def get_workload_snapshot(self, workload_set_id: str) -> "WorkloadSnapshot":
        """返回仿真引擎使用的只读任务快照。"""
```

### 6.1 历史映射规则

- 优先使用 historical_instance 作为调度单元。
- 实例通过 `job_name + task_name` 取得计划资源。
- 历史百分比在映射时转换为 GPU 当量和 CPU 核。
- 缺少 plan 资源或无法形成合法 ResourceVector 的记录不得静默映射。
- `expand_tasks_without_instances` 必须显式配置并记录在输入哈希中。
- 工作负载集冻结后不可修改。

## 7. 调度规则接口

```python
@dataclass(frozen=True)
class SchedulableTaskSnapshot:
    task_id: str
    submit_time: float
    priority: int
    estimated_duration: float
    demand: TaskDemand
    sequence_no: int


@dataclass(frozen=True)
class ServerSnapshot:
    server_id: str
    name: str
    gpu_type: str
    capacity: ResourceVector
    allocated: ResourceVector
    status: str


@dataclass(frozen=True)
class PlacementDecision:
    server_id: str | None
    fit_score: float | None
    reason: str


class TaskOrderingPolicy(Protocol):
    name: str

    def order(
        self,
        tasks: tuple[SchedulableTaskSnapshot, ...],
        now: float,
    ) -> tuple[SchedulableTaskSnapshot, ...]:
        """返回确定性排序后的候选任务。"""


class PlacementPolicy(Protocol):
    name: str

    def choose_server(
        self,
        task: SchedulableTaskSnapshot,
        servers: tuple[ServerSnapshot, ...],
    ) -> PlacementDecision:
        """只做资源匹配，不决定任务排序。"""
```

实现：

- `FIFOOrderingPolicy`
- `SJFOrderingPolicy`
- `PriorityOrderingPolicy`
- `FirstFitPlacementPolicy`
- `BestFitPlacementPolicy`

策略必须是无状态或只读状态，输入相同则输出相同。

## 8. 仿真引擎

```python
@dataclass(frozen=True)
class SimulationInput:
    run_id: str
    workload: "WorkloadSnapshot"
    cluster: "ClusterSnapshot"
    scheduler: "SchedulerSnapshot"
    random_seed: int
    engine_version: str


@dataclass(frozen=True)
class SimulationFrame:
    run_id: str
    simulation_time: float
    status: str
    waiting_count: int
    running_count: int
    completed_count: int
    total_gpu_capacity: float
    allocated_gpu: float
    recent_events: tuple[dict, ...]
    task_states: tuple[dict, ...]
    server_states: tuple[dict, ...]


@dataclass(frozen=True)
class StepResult:
    frame: SimulationFrame
    finished: bool
    emitted_events: tuple[dict, ...]


class SimulationEngine(Protocol):
    def initialize(self, input: SimulationInput) -> None:
        """从冻结快照建立初始事件和资源状态。"""

    def step(self) -> StepResult:
        """推进到下一个确定性事件批次。"""

    def run_until_pause_or_end(self, max_events: int | None = None) -> StepResult:
        """连续运行，达到暂停/结束/保护上限时返回。"""

    def pause(self) -> None: ...

    def resume(self) -> None: ...

    def reset(self) -> None: ...

    def cancel(self) -> None: ...

    def get_frame(self) -> SimulationFrame:
        """返回展示层可直接使用的当前只读状态。"""

    def get_result(self) -> "SimulationResult":
        """返回最终任务、事件、指标输入和结果哈希。"""
```

### 8.1 关键约束

- `step()` 必须原子地完成一个事件时间点的资源释放、到达处理和若干调度决策。
- 播放速度不属于 `SimulationEngine` 接口。
- `run_until_pause_or_end` 的 `max_events` 是防死循环保护，不是业务结果的一部分。
- `reset()` 只能重置尚未完成的运行；已完成运行必须创建新 run。
- UI 不可修改引擎内部任务或服务器对象。

## 9. 评价与比较

```python
@dataclass(frozen=True)
class MetricDefinition:
    name: str
    formula_version: str
    unit: str
    description: str


class EvaluationService(Protocol):
    def calculate_metrics(
        self,
        run_id: str,
        metric_names: tuple[str, ...] | None = None,
    ) -> "RunMetrics":
        """按版本化公式计算并保存指标。"""

    def compare_runs(
        self,
        run_ids: tuple[str, ...],
    ) -> "ComparisonResult":
        """检查输入兼容性，再比较指标和分布。"""

    def get_metric_definitions(self) -> tuple[MetricDefinition, ...]: ...
```

兼容性检查至少比较：

- dataset_version_id
- workload_set_id
- cluster_config_id
- 任务到达序列
- random_seed（要求确定性比较时）
- 指标公式版本

不兼容时返回明确原因，不做“部分平均”或强行比较。

## 10. AI 建议

```python
@dataclass(frozen=True)
class RecommendationRequest:
    run_id: str
    focus: str  # CONGESTION | FRAGMENTATION | STRATEGY | THROUGHPUT


@dataclass(frozen=True)
class Recommendation:
    summary: str
    reasoning: str
    rule_version: str
    evidence: tuple["EvidenceRef", ...]
    suggested_config_patch: dict | None


class AdvisorService(Protocol):
    def recommend(self, request: RecommendationRequest) -> tuple[Recommendation, ...]:
        """基于真实指标返回可追溯建议。"""

    def explain(self, run_id: str, question: str) -> Recommendation:
        """后续可接大模型；首版按规则模板生成。"""
```

AI 模块：

- 只读运行、指标和事件。
- 不调用调度器改变已完成实验。
- 建议接受后由配置模块创建新的 DRAFT。
- 没有证据时返回“无法判断”，不得编造。

## 11. 模块依赖矩阵

| 调用方 | 允许依赖 | 禁止依赖 |
|---|---|---|
| app/UI | 各模块应用接口、只读查询 | ORM 实体、其他模块内部表 |
| data_catalog | 共享值对象、原始文件、历史表 | 调度、仿真、AI |
| cluster_config | 共享值对象、配置表 | 历史实例写操作、仿真内部状态 |
| workload | 历史查询契约、共享值对象、工作负载表 | 直接读取历史表内部 ORM |
| scheduling | 共享值对象和调度快照 | 数据库、Streamlit、历史表 |
| simulation | scheduling 接口、冻结快照、运行表 | UI、历史原始 CSV |
| evaluation | 仿真只读结果、指标定义 | 改写运行状态 |
| ai_advisor | evaluation、事件和配置只读投影 | 写调度结果 |
| persistence | 数据库基础设施 | 业务决策 |

## 12. 测试接口

必须存在的测试替身或确定性输入：

- 固定时间提供器。
- 固定 ID 生成器。
- 固定随机种子。
- 内存历史数据目录替身。
- 内存工作负载/集群快照。
- 确定性调度策略。
- 小型事件序列样例。

核心测试断言：

```text
given queue = [T1(submit=0), T2(submit=1)]
when FIFO.order()
then [T1, T2]

given server capacity = (8 GPU, 96 CPU, 512 GB)
and task demand = (1 GPU, 6 CPU, 32 GB)
when allocate()
then allocated <= capacity

given identical SimulationInput and random_seed
when run twice
then event sequence and result_hash are equal
```

## 13. 接口演进规则

- 请求/响应结构是模块公开契约。
- 不在公开契约中暴露 SQLAlchemy 模型。
- 新增字段优先保持向后兼容；删除或改变语义需要版本化。
- 调度策略预设和指标公式均带版本。
- 实验记录保存接口/引擎版本，确保旧结果可解释。
