# 阶段 1：数据库与业务模型建议

> 本文是基于真实字段约束提出的阶段 2 设计输入，不是最终 ER 图或建表脚本。

## 1. 设计目标

数据库必须同时满足四类需求：

1. 保留真实历史数据的完整语义和异常。
2. 支持用户配置独立的虚拟 GPU 集群。
3. 保存可复现的调度实验和仿真过程。
4. 让所有分析指标、图表和 AI 建议都能追溯到具体数据版本和实验配置。

核心原则：真实历史数据、系统配置数据、仿真生成数据不在同一批表中混用。

## 2. 推荐的数据分层

### 2.1 原始数据层

- 文件：TAR + CSV。
- 不变式：只读，不覆盖。
- 元数据：文件 SHA-256、来源 URL、下载日期、解压日期、行数、列映射版本。

### 2.2 历史标准化层

存储从七张 CSV 导入的结构化历史数据：

- `dataset_version`
- `import_batch`
- `historical_job`
- `historical_task`
- `historical_instance`
- `historical_sensor`
- `historical_group_tag`
- `historical_machine_spec`
- `historical_machine_metric`

每条记录保留：

- `source_row_no`：源 CSV 行号，便于回溯。
- `dataset_version_id`：数据版本。
- `import_batch_id`：导入批次。
- `raw_status`：原始状态。
- 原始字段 + 派生字段。

### 2.3 配置层

用户创建的仿真环境：

- `gpu_server`
- `gpu_server_resource`
- `cluster_config`
- `scheduler_config`

它们与 `historical_machine_spec` 完全分离。用户可以参考真实机器模板创建虚拟服务器，但修改不会影响历史规格。

### 2.4 仿真运行层

- `simulation_run`
- `simulation_task`
- `simulation_assignment`
- `simulation_event`
- `simulation_snapshot`
- `simulation_resource_sample`
- `simulation_metric`
- `simulation_recommendation`

所有记录带 `run_id`。同一配置必须生成可复现的实验版本。

## 3. 历史表建议

### 3.1 `historical_job`

关键字段：

- `job_id`：内部主键
- `job_name`：唯一，官方业务键
- `inst_id`：官方 job_id，唯一
- `user_name`
- `raw_status`
- `business_status`
- `relative_start_second`
- `relative_end_second`
- `duration_second`
- `has_started`
- `has_finished`
- `is_successful`
- `source_row_no`

索引：

- `(job_name)`
- `(inst_id)`
- `(raw_status, relative_start_second)`
- `(user_name, relative_start_second)`

### 3.2 `historical_task`

关键字段：

- `task_id`
- `job_name`
- `task_name`
- `inst_num`
- `raw_status`
- `business_status`
- `relative_start_second`
- `relative_end_second`
- `duration_second`
- `plan_cpu_percent`
- `plan_cpu_cores`
- `plan_mem_gb`
- `plan_gpu_percent`
- `plan_gpu_equivalent`
- `gpu_type`
- `has_resource_request`
- `source_row_no`

唯一键：`(job_name, task_name)`。

### 3.3 `historical_instance`

关键字段：

- `instance_id`
- `job_name`
- `task_name`
- `inst_name`
- `worker_name`
- `inst_id`
- `raw_status`
- `business_status`
- `relative_start_second`
- `relative_end_second`
- `duration_second`
- `machine`
- `is_assigned_to_machine`
- `source_row_no`

说明：Waiting、Ready 状态的 machine 和 worker_name 合法为空，不应转换为空字符串后参与唯一键。

### 3.4 `historical_sensor`

- `sensor_id`
- `worker_name`
- `job_name`
- `task_name`
- `inst_id`
- `machine`
- `gpu_name`
- `cpu_usage_percent`
- `gpu_work_util_raw`
- `avg_mem_gb`
- `max_mem_gb`
- `avg_gpu_mem_gb`
- `max_gpu_mem_gb`
- `read_bytes_avg`
- `write_bytes_avg`
- `read_count_avg`
- `write_count_avg`
- `source_row_no`

不直接把 `gpu_work_util_raw` 重命名为 `gpu_utilization_pct`，避免误解口径。

### 3.5 `historical_group_tag`

- `group_tag_id`
- `inst_id`
- `user_name`
- `gpu_type_spec`
- `group_name`
- `workload`
- `source_row_no`

`gpu_type_spec` 和 `workload` 允许为空，不作为必填分类。

### 3.6 `historical_machine_spec`

- `machine`
- `gpu_type`
- `cap_cpu_cores`
- `cap_mem_gb`
- `cap_gpu`
- `is_cpu_only`

### 3.7 `historical_machine_metric`

- `machine_metric_id`
- `worker_name`
- `machine`
- `relative_start_second`
- `relative_end_second`
- `machine_cpu_iowait_pct`
- `machine_cpu_kernel_pct`
- `machine_cpu_usr_pct`
- `machine_gpu_raw`
- `machine_gpu_normalized`
- `machine_load_1`
- `machine_net_receive_bytes_avg`
- `machine_num_worker_avg`
- `machine_cpu_pct`
- `source_row_no`

`machine_gpu_raw` 必须保留；`machine_gpu_normalized` 是由 `raw / (100 × cap_gpu)` 得到的派生值。归一化异常不能被无提示裁剪。

## 4. 配置与仿真模型建议

### 4.1 服务器配置

`gpu_server`

- `server_id`
- `name`
- `gpu_type`
- `gpu_count`
- `cpu_cores`
- `memory_gb`
- `status`
- `template_machine`：可选，引用真实机器模板
- `config_version`

`gpu_server_resource`

- `server_id`
- `allocated_gpu`
- `allocated_cpu`
- `allocated_memory_gb`

约束：

- 已分配资源不得超过容量。
- 资源模型以服务器为独立容量边界，不做全集群无约束池化。
- GPU 类型匹配需求时才能分配；后续阶段确认是否允许混合型号。

### 4.2 调度配置

`scheduler_config`

- `strategy`：FIFO、SJF、PRIORITY、BEST_FIT
- `task_ordering_rule`
- `server_placement_rule`
- `tie_breaker`
- `allow_backfill`
- `random_seed`
- `config_json`

必须分开表达两件事：

1. 任务排序规则：FIFO、SJF、Priority。
2. 服务器放置规则：First Fit、Best Fit 等。

Best Fit 不是任务排序策略，不能和 FIFO/SJF 混成一个维度。

### 4.3 仿真任务

`simulation_task`

- `task_id`
- `run_id`
- `name`
- `gpu_required`
- `cpu_required`
- `memory_required_gb`
- `priority`
- `submit_time`
- `estimated_duration`
- `source_type`：HISTORICAL_REPLAY / USER_CREATED
- `source_task_id`：历史回放时引用历史任务
- `status`

### 4.4 仿真实验

`simulation_run`

- `run_id`
- `run_name`
- `dataset_version_id`
- `cluster_config_id`
- `scheduler_config_id`
- `task_set_id`
- `random_seed`
- `started_at`
- `finished_at`
- `status`
- `engine_version`
- `result_hash`

`result_hash` 用于验证相同配置和种子是否生成一致结果。

### 4.5 调度记录

`simulation_assignment`

- `assignment_id`
- `run_id`
- `task_id`
- `server_id`
- `decision_time`
- `gpu_allocated`
- `cpu_allocated`
- `memory_allocated_gb`
- `reason`
- `decision_sequence`

`simulation_event`

- `event_id`
- `run_id`
- `event_time`
- `event_type`：TASK_SUBMITTED / TASK_QUEUED / TASK_SCHEDULED / TASK_STARTED / TASK_COMPLETED / TASK_CANCELLED / RESOURCE_RELEASED / SCHEDULE_FAILED
- `task_id`
- `server_id`
- `payload_json`
- `sequence_no`

事件日志用于审计和动态回放，不应用来替代当前状态快照。

### 4.6 资源时间线

`simulation_snapshot`

- 定期保存完整资源状态，支持快速跳转和调试。

`simulation_resource_sample`

- 按仿真时间区间记录每台服务器的 GPU、CPU、内存使用率。
- 支持图表降采样，避免每个事件都产生前端回放压力。

### 4.7 评价指标

`simulation_metric`

- `run_id`
- `metric_name`
- `metric_value`
- `dimension_json`
- `formula_version`

至少包含：

- average_wait_time
- average_turnaround_time
- makespan
- gpu_average_utilization
- cpu_average_utilization
- memory_average_utilization
- completion_rate
- timeout_rate
- fairness_index

指标必须与 `run_id`、公式版本和样本范围绑定。

## 5. AI 建议可追溯模型

`simulation_recommendation`

- `recommendation_id`
- `run_id`
- `recommendation_type`
- `summary`
- `reasoning`
- `evidence_json`
- `model_or_rule_version`
- `created_at`
- `accepted_by_user`

`evidence_json` 保存引用的实际指标和事件 ID。规则建议和未来大模型建议都必须引用证据，不能生成无来源的 GPU 使用率或实验结果。

AI 建议只能生成候选项，不能绕过资源约束直接修改调度结果。

## 6. 事务与一致性

- 服务器资源配置修改使用短事务。
- 仿真运行不应在整个运行期间持有数据库长事务。
- 调度决策在内存中完成，按批次持久化事件、分配和快照。
- 每次仿真开始前冻结任务集、集群配置和调度参数版本。
- 同一 `run_id` 的指标只能由指定引擎版本重算。
- 取消仿真时保留已产生事件，并将运行状态设为 CANCELLED。
- 不允许业务层直接修改已完成实验的任务执行记录。

## 7. 索引建议

必须优先建立：

- job：`job_name`、`inst_id`、`(raw_status, relative_start_second)`
- task：`(job_name, task_name)`、`(raw_status, relative_start_second)`
- instance：`worker_name`、`(job_name, task_name)`、`machine`
- sensor：`worker_name`、`machine`
- machine_metric：`worker_name`、`machine`
- simulation_task：`(run_id, status, submit_time)`
- simulation_event：`(run_id, sequence_no)`
- simulation_assignment：`(run_id, decision_sequence)`
- simulation_resource_sample：`(run_id, simulation_time)`

索引应依据真实查询计划建立，不只按“外键就加索引”机械处理。

## 8. 存储策略建议

### 推荐：混合策略

- 小表全量：job、task、group_tag、machine_spec。
- 大表支持全量或确定性分层抽样：instance、sensor、machine_metric。
- 每个数据集版本记录导入模式、抽样规则、覆盖率和哈希。
- 原型阶段默认抽样以保证交互速度，最终验收支持全量导入。

### SQLite 边界

SQLite 足以支撑单机课程项目和中等规模查询，但需要：

- 分块导入。
- 批量事务提交。
- 预聚合常用统计。
- 对结果分页。
- 避免对大表执行无索引的全表扫描。
- 不把每次仿真 tick 都立即写入 SQLite。

## 9. 需要用户或阶段 2 确认的设计问题

1. 首个可运行版本默认使用全量历史数据还是分层抽样？
2. GPU 类型是否必须严格匹配，还是允许兼容型号降级？
3. 任务是否允许跨服务器拆分，还是每个任务只能放置在一台服务器？
4. 内存单位沿用历史数据 GB，还是允许 MiB 输入并统一转换？
5. 失败任务是否进入仿真回放，还是只作为历史分析样本？
6. 是否把未完成历史任务视为“到达但未完成”，参与调度压力测试？
7. 公平性指标按用户、group、workload 还是多维度计算？

这些问题应在阶段 2 系统分析中明确，不能由实现代码暗中决定。
