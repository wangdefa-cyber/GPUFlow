# 阶段 4：最小可运行闭环

- 阶段：数据导入 → 资源配置 → 任务调度 → 过程展示 → 效果评价
- 日期：2026-11-22
- 状态：完成

## 1. 实现范围

阶段 4 已实现：

1. SQLite 数据库和 SQLAlchemy 持久化层。
2. 虚拟 GPU 服务器配置持久化。
3. 用户仿真任务持久化。
4. 从真实阿里巴巴 instance + task + job 表导入历史回放样本。
5. FIFO、SJF、Priority 排序规则。
6. First Fit 和 Best Fit 放置规则。
7. GPU、CPU、内存和 GPU 型号多资源约束。
8. 确定性离散事件仿真引擎。
9. 任务到达、调度、开始、完成和受阻事件。
10. 资源释放和利用率采样。
11. 等待、周转、Makespan、利用率、完成率、超时率和 Jain 公平性指标。
12. Plotly 任务甘特图。
13. 基于真实资源采样的动态时间线。
14. 实验事件、任务结果、指标和样本持久化。
15. 历史实验回看。

## 2. 数据库实现

数据库默认位置：

```text
artifacts/gpuflow.db
```

可通过环境变量覆盖：

```powershell
$env:GPUFLOW_DB_PATH = "D:\path\to\gpuflow.db"
```

已实现表：

- `dataset_version`
- `gpu_server`
- `simulation_task`
- `scheduler_config`
- `simulation_run`
- `simulation_event`
- `run_task_result`
- `run_metric`
- `resource_sample`
- `app_setting`

设计特征：

- SQLite 开启外键、WAL 和 NORMAL 同步。
- 服务器、用户任务和调度配置为系统配置数据。
- 历史回放任务标记 `HISTORICAL_REPLAY`。
- 用户任务标记 `USER_CREATED`。
- 每次实验保存任务和服务器冻结快照。
- 事件、逐任务结果、指标和资源采样与 `run_id` 绑定。
- 已完成实验不原地修改。

## 3. 真实历史工作负载导入

输入：

- `pai_instance_table.csv`
- `pai_task_table.csv`
- `pai_job_table.csv`

导入步骤：

1. 读取前若干真实 instance 行。
2. 保留 `Terminated`、worker/machine 非空、时间非空且时长大于 0 的实例。
3. 扫描 task 表，按 `job_name + task_name` 关联真实资源计划。
4. 扫描 job 表，补充真实用户标识。
5. 将 `plan_gpu`、`plan_cpu` 百分比转换为 GPU/CPU 当量。
6. 将实例真实时长作为预计运行时长。
7. 以样本最早实例开始时间为 0，构造相对到达时间。
8. 写入新的数据集版本和只读历史回放任务。

明确假设：

- 历史 task 没有优先级，统一使用中性优先级 5。
- 当前阶段使用文件前部的有界终止实例样本，不是全量回放。
- 不允许在未匹配到有效资源计划时编造字段。
- 同一文件样本通过版本码和任务来源保持可追溯。

## 4. 调度实现

### 4.1 排序

FIFO：

```text
submit_time → sequence_no → task_id
```

SJF：

```text
estimated_duration → submit_time → sequence_no → task_id
```

Priority：

```text
-priority → submit_time → sequence_no → task_id
```

### 4.2 放置

First Fit：

- 服务器按名称和 ID 稳定排序。
- 返回第一个满足全部约束的服务器。

Best Fit：

```text
score = Σ weight_r × remaining_after_r / capacity_r
```

选择 score 最小的服务器。默认 GPU/CPU/内存权重均为 1。

### 4.3 多资源约束

任务必须同时满足：

- GPU 型号匹配。
- 剩余 GPU ≥ 任务 GPU 需求。
- 剩余 CPU ≥ 任务 CPU 需求。
- 剩余内存 ≥ 任务内存需求。

不足时不得强制分配。

### 4.4 队头规则

- `allow_skip_head=false`：只尝试当前排序队列头部。
- `allow_skip_head=true`：按排序顺序寻找后续可放置任务。
- 默认关闭，保留严格 FIFO 语义。

## 5. 离散事件引擎

事件优先级：

```text
同一仿真时刻：完成事件 → 到达事件 → 调度决策
```

运行流程：

```text
初始化到达事件
→ 弹出最早事件时间
→ 处理同刻完成与到达
→ 释放完成任务资源
→ 按策略放置等待任务
→ 记录分配与启动事件
→ 生成完成事件
→ 记录资源采样
→ 继续下一事件时间
```

引擎不依赖 Streamlit，可在命令行和测试中独立运行。

## 6. 动态过程展示

动态页提供：

- 当前实验选择。
- 实验输入和结果哈希。
- 拖动仿真时间读取最近资源采样。
- 当前运行任务数。
- GPU、CPU、内存已分配量。
- GPU、CPU、内存利用率曲线。
- 按服务器着色的任务甘特图。
- 逐任务结果。
- 完整调度事件日志。
- 受阻任务提示。

时间线数据来自 `resource_sample`，甘特图来自 `run_task_result`，不是前端随机动画。

## 7. 评价指标

已实现：

- 平均等待时间
- 平均周转时间
- Makespan
- GPU 平均利用率
- CPU 平均利用率
- 内存平均利用率
- 完成率
- 超时率
- Jain 公平性指数
- 完成与受阻任务数

公式版本：`metrics-v1`。

## 8. 验证结果

自动化测试：

```text
18 passed
```

覆盖：

- FIFO、SJF、Priority 排序。
- First Fit、Best Fit 放置。
- 多资源阻塞。
- 资源释放。
- 确定性复现。
- SQLite 初始化、配置和闭环。
- 九个 Streamlit 页面在存在真实仿真结果时正常渲染。

真实历史样本冒烟测试：

```text
历史样本任务：20
用户任务：6
用户任务 Makespan：10,800 秒
用户任务平均等待：500 秒
用户任务 GPU 利用率：25.43%
用户任务完成率：100%
历史回放 Makespan：53,374 秒
历史回放平均等待：78.4 秒
历史回放 GPU 利用率：0.16%
历史回放完成率：100%
```

历史样本 GPU 利用率较低，是因为该样本任务稀疏且虚拟集群容量较大，不是指标计算错误。

Streamlit Agent API：

```text
status = ready
exceptions = 0
server log = no warnings or traceback
```

## 9. 当前限制

- 历史导入当前使用有界文件前部终止实例样本，并非全量随机或分层抽样。
- 历史优先级统一使用默认值 5。
- 仿真一次性计算完成，尚未提供交互式暂停、继续和单步控制。
- 时间线通过拖动资源采样回看，不是实时逐帧动画。
- 策略对比页仍属于阶段 5。
- AI 规则引擎仍属于阶段 6。
- 尚未实现任务取消和运行中失败注入。

## 10. 阶段 5 输入

下一阶段应重点完成：

1. 历史样本分层抽样和覆盖率展示。
2. 暂停、继续、单步和重置控制。
3. 更严格的队列阻塞与不可调度分析。
4. 多策略同条件批量实验。
5. 策略对比表和图表。
6. 资源碎片、等待分位数和更多辅助指标。
7. 实验复现与结果哈希校验。
