# 阶段 2：调度评价指标定义

- 公式版本：`metrics-v1`
- 适用范围：同一仿真运行内的策略评价，以及输入条件一致的跨策略比较
- 数据来源：仿真事件、任务状态、资源分配和资源采样；不得使用历史监控值替代

## 1. 符号

| 符号 | 含义 |
|---|---|
| `N` | 实验任务总数 |
| `C` | 完成任务集合 |
| `T_i^submit` | 任务 i 的提交/到达仿真时间 |
| `T_i^start` | 任务 i 首次开始运行时间 |
| `T_i^end` | 任务 i 完成时间 |
| `W_i` | 任务 i 的等待时长 |
| `R_i` | 任务 i 的周转时长 |
| `G_i(t)` | t 时刻已分配 GPU 当量 |
| `C_gpu` | 集群 GPU 总容量 |
| `M` | Makespan |
| `deadline_i` | 可选任务截止时间 |
| `SLA_wait` | 配置的等待 SLA |

## 2. 任务级指标

### 2.1 等待时长

对已开始任务：

```text
W_i = max(0, T_i^start - T_i^submit)
```

对未开始任务，等待时长在 Makespan 时仍是 censored（截断），不能直接当成已完成的等待样本。

主指标：

```text
Average Wait Time = mean(W_i for i in C)
```

同时报告：

- 已开始任务平均等待时长。
- 等待时长 P50、P90、P95、P99。
- 未开始任务数。

### 2.2 周转时长

```text
R_i = T_i^end - T_i^submit,  i in C
Average Turnaround Time = mean(R_i for i in C)
```

### 2.3 Makespan

设最早提交时间为 `T_0`：

```text
T_0 = min(T_i^submit)
M = max(T_i^end for i in C) - T_0
```

若没有任何任务完成，Makespan 返回 `null`，不能伪造为 0。

## 3. 完成与可靠性

### 3.1 完成率

```text
Completion Rate = |C| / N
```

取消、失败、未调度任务均不属于完成集合。

### 3.2 超时率

任务 i 被视为超时的条件：

1. 有显式 `deadline_i`：`T_i^end > deadline_i`。
2. 无显式截止时间：`W_i > SLA_wait`。
3. 未开始或未完成且已超过等待 SLA：也计为超时。

```text
Timeout Rate = count(timeout tasks) / N
```

必须同时展示超时判定使用的 `SLA_wait` 和截止时间来源。

## 4. 利用率

### 4.1 时间加权 GPU 平均利用率

```text
GPU Utilization = (∫_0^M G_i(t) dt) / (C_gpu × M)
```

注意：

- `G_i(t)` 来自仿真分配，而不是历史 `machine_gpu`。
- 资源采样按时间区间积分；无采样的区间不能默认为 0。
- 若存在资源容量变更，应使用运行冻结配置；首版容量固定。

CPU 和内存同理：

```text
CPU Utilization = ∫ CPU_allocated(t) dt / (CPU_capacity × M)
Memory Utilization = ∫ Memory_allocated(t) dt / (Memory_capacity × M)
```

所有利用率同时报告时间加权均值和运行期间最大值。

### 4.2 单服务器利用率

```text
Server GPU Utilization_s = ∫ G_s(t) dt / (C_s × M)
```

用于识别热点服务器和资源碎片，不应只展示集群总利用率。

## 5. 公平性

首版使用 Jain 公平指数。

按用户 u 汇总 GPU 分配量：

```text
x_u = Σ_i (GPU_i × (T_i^end - T_i^start))   for tasks of user u
J = (Σ_u x_u)^2 / (n × Σ_u x_u^2)
```

- `n` 是参与评价的用户数。
- `J = 1` 表示完全平均。
- 所有用户分配量均为 0 时返回 `null`，不能宣称完全公平。
- 首版默认按用户；后续支持 group 和 workload。
- 缺失用户标签的任务进入 `UNKNOWN` 分组，并在结果中显示。

## 6. 辅助指标

### 6.1 队列长度

在每个资源采样点记录：

- waiting_count
- running_count
- completed_count
- blocked_count

报告最大值、P95 和均值。

### 6.2 资源碎片

对每台服务器在采样时刻计算剩余 GPU 比例。碎片指标用于解释“总 GPU 足够但大任务无法放置”的情况：

```text
GPU Fragmentation Ratio = 1 - max_fit_task_gpu / total_free_gpu
```

没有可放置任务时返回 `null`，不能当作 0 碎片。

### 6.3 策略评价结果

每个策略至少返回：

- average_wait_time
- average_turnaround_time
- makespan
- gpu_average_utilization
- cpu_average_utilization
- memory_average_utilization
- completion_rate
- timeout_rate
- fairness_index
- 等待/周转分位数

## 7. 策略比较规则

只有以下输入一致时才允许直接比较：

- dataset_version_id
- workload_set_id
- 任务到达序列和任务数量
- cluster_config_id
- random_seed
- 指标公式版本

若集群容量、任务集合或到达序列不同，必须标为“不可直接比较”，并说明差异。

## 8. 计算示例

假设集群有 2 张 GPU，Makespan 为 10 秒：

- 0–5 秒分配 2 张 GPU
- 5–10 秒分配 0 张 GPU

```text
积分 = 2×5 + 0×5 = 10 GPU·秒
容量上限 = 2×10 = 20 GPU·秒
GPU 利用率 = 10 / 20 = 50%
```

任务示例：

- T1：提交 0，开始 2，完成 8
- T2：提交 1，开始 3，完成 9

```text
W1 = 2, W2 = 2 → 平均等待 = 2
R1 = 8, R2 = 8 → 平均周转 = 8
M = 9 - 0 = 9
```

## 9. 指标质量要求

1. 公式结果必须绑定 `run_id` 和 `formula_version`。
2. 不允许把未完成任务的等待时间伪装为已完成的等待样本。
3. 指标缺失时返回 `null` 并说明原因。
4. 图表必须同时展示样本范围和单位。
5. 同一指标重算产生新版本记录，不覆盖旧结果。
