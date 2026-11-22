# 阶段 1：七张表数据字典

- 数据来源：阿里巴巴 `cluster-trace-gpu-v2020`
- 官方说明快照：`docs/reference/alibaba_gpu_trace_readme.md`
- 实际文件：`data/<table>/<table>.csv`
- 文件格式：无表头 CSV，逗号分隔
- 审计方法：Pandas 分块读取，默认块大小 200,000 行

## 1. 通用口径

### 1.1 时间

`start_time`、`end_time` 均为脱敏后的相对秒数，不是可直接解释为真实日期的 Unix 时间。官方说明指出，它们保留原数据中一天内的时刻和星期关系，但日期、月份、年份是虚构的。

在本系统中应将其保存为：

- `relative_start_second`
- `relative_end_second`
- `duration_second = end_time - start_time`

如果界面需要显示日历日期，必须明确标注为“脱敏时间”，不得冒充真实日期。

### 1.2 资源单位

- `plan_cpu`：CPU 核数百分比。`600` 表示 6 个 vCPU。
- `plan_gpu`：GPU 数量百分比。`50` 表示 0.5 张 GPU，`100` 表示 1 张 GPU，`800` 表示 8 张 GPU。
- `plan_mem`：GB。
- `cap_cpu`：CPU 核数。
- `cap_mem`：GB。
- `cap_gpu`：GPU 数量。
- `cpu_usage`、`gpu_wrk_util`：需要使用实际分布验证口径，不能简单假定永远处于 0–100。
- `machine_gpu`：机器级 GPU 指标，原始值可超过 100，必须结合 `cap_gpu` 解释。
- `read`、`write`：字节数。
- `read_count`、`write_count`：读写次数。

### 1.3 数据类别

系统后续必须区分：

| 类别 | 来源 | 示例 |
|---|---|---|
| A. 真实历史数据 | 七张官方表 | 历史 job、task、instance、sensor |
| B. 系统配置数据 | 用户在系统中创建 | 虚拟服务器、容量、调度参数 |
| C. 仿真生成数据 | 仿真引擎输出 | 仿真任务、分配、时间线、利用率 |

## 2. `pai_job_table`

- 行数：1,055,501
- 列数：6
- 文件大小：127.11 MB
- 全行重复：0
- 主键：`job_name`，非空唯一
- `job_name` 与 `inst_id` 实际为 1:1，均有 1,055,501 个非空唯一值

| 字段 | 类型 | 缺失 | 业务含义 | 关系/备注 |
|---|---|---:|---|---|
| job_name | string | 0 | 脱敏后的作业名称 | 与 task、instance、sensor 关联 |
| inst_id | string | 0 | 官方建议视作 job_id | 与 group_tag、instance、sensor 关联 |
| user | string | 0 | 脱敏用户标识 | 用于公平性和用户维度分析 |
| status | string | 0 | 作业状态 | 见状态表 |
| start_time | float64 | 3,663 | 作业提交时间，相对秒 | Waiting 作业为空 |
| end_time | float64 | 296,420 | 作业完成时间，相对秒 | 未完成/失败作业可能为空 |

作业状态分布：

| 状态 | 行数 |
|---|---:|
| Terminated | 732,355 |
| Failed | 256,555 |
| Running | 62,928 |
| Waiting | 3,663 |

典型记录：

```text
87a79c6373f7439d82f32a1c,38e2d718...,74238accb90b,Running,1053513.0,
```

## 3. `pai_task_table`

- 行数：1,261,050
- 列数：10
- 文件大小：108.15 MB
- 全行重复：0
- 实际任务键：`job_name + task_name`，唯一
- 有 1,055,501 个唯一 `job_name`，与 job 表一一覆盖
- 有 130 个任务没有对应 instance，数量与 `inst_num` 缺失行数一致

| 字段 | 类型 | 缺失 | 业务含义 | 关系/备注 |
|---|---|---:|---|---|
| job_name | string | 0 | 作业名称 | 关联 job |
| task_name | string | 0 | 任务角色/名称 | 如 worker、ps、tensorflow |
| inst_num | float64 | 130 | 任务启动的实例数 | 不应直接当作资源量 |
| status | string | 0 | 任务状态 | 见状态表 |
| start_time | float64 | 3,714 | 任务启动时间，相对秒 | job 提交到最早 task 启动的差可近似排队时间 |
| end_time | float64 | 349,561 | 任务完成时间，相对秒 | 失败和未完成任务常为空 |
| plan_cpu | float64 | 18,454 | 请求 CPU 核数百分比 | 除以 100 得 vCPU |
| plan_mem | float64 | 18,454 | 请求内存 GB | 可用于内存约束 |
| plan_gpu | float64 | 223,965 | 请求 GPU 数量百分比 | 除以 100 得 GPU 当量 |
| gpu_type | string | 217,738 | 分配/请求的 GPU 类型 | 含 MISC、T4、P100、V100、V100M32 |

任务状态分布：

| 状态 | 行数 |
|---|---:|
| Terminated | 885,073 |
| Failed | 256,762 |
| Running | 115,501 |
| Waiting | 3,714 |

资源请求分位数：

| 字段 | P50 | P90 | P95 | P99 | 最大值 |
|---|---:|---:|---:|---:|---:|
| plan_cpu | 600 | 1,000 | 1,800 | 2,000 | 9,000 |
| plan_mem | 29.296875 | 29.296875 | 58.59375 | 78.125 | 400 |
| plan_gpu | 50 | 100 | 100 | 400 | 800 |
| task duration | 621 s | 12,501 s | 23,731 s | 71,147.24 s | 639,766 s |

任务角色中，`tensorflow` 621,415 行、`worker` 275,785 行、`ps` 183,283 行，是最主要的角色。

## 4. `pai_instance_table`

- 行数：7,522,002
- 列数：9
- 文件大小：1,883.68 MB
- 全行重复：0
- `job_name + task_name + inst_name` 非空唯一值：6,846,883
- 非空唯一 `worker_name`：7,164,359
- 非空唯一 `inst_id`：1,055,432

| 字段 | 类型 | 缺失 | 业务含义 | 关系/备注 |
|---|---|---:|---|---|
| job_name | string | 0 | 作业名称 | 关联 job |
| task_name | string | 0 | 任务名称 | 与 job_name 组成 task 键 |
| inst_name | string | 0 | 任务内实例名称 | 与 job/task 组成业务实例键 |
| worker_name | string | 331,057 | 更细粒度的实例标识 | 关联 sensor、machine_metric |
| inst_id | string | 0 | 官方建议视作 job_id | 关联 job、group_tag、sensor |
| status | string | 0 | 实例状态 | 比 job/task 状态多 Interrupted、Ready |
| start_time | float64 | 1,773,468 | 实例启动时间，相对秒 | Waiting/Interrupted 等状态常为空 |
| end_time | float64 | 2,267,582 | 实例完成时间，相对秒 | 未完成/中断等状态常为空 |
| machine | string | 331,057 | 所在机器 | 关联 machine_spec、sensor、machine_metric |

实例状态分布：

| 状态 | 行数 |
|---|---:|
| Terminated | 4,757,371 |
| Failed | 969,975 |
| Running | 809,664 |
| Interrupted | 654,022 |
| Waiting | 323,840 |
| Ready | 7,130 |

重要质量特征：

- Waiting、Ready 的实例没有 worker_name 和 machine。
- Waiting、Interrupted、Ready 的 start_time 全部为空。
- Running 的 end_time 全部为空。
- Terminated 的 end_time 仅有 11 行为空。
- 因此不能简单用 `end_time - start_time` 对所有行计算运行时长。

## 5. `pai_sensor_table`

- 行数：3,033,232
- 列数：16
- 文件大小：1,007.94 MB
- 全行重复：0
- `worker_name` 与 `worker_name + gpu_name` 均为 3,033,232 个唯一非空值
- 只覆盖 3,033,232 个实例，约占 instance 非空 worker 的 42.14%

| 字段 | 类型 | 缺失 | 业务含义 |
|---|---|---:|---|
| job_name | string | 0 | 作业名称 |
| task_name | string | 0 | 任务名称 |
| worker_name | string | 0 | 实例唯一标识 |
| inst_id | string | 0 | 作业 ID |
| machine | string | 0 | 机器 |
| gpu_name | string | 0 | 该实例对应的 GPU 设备名 |
| cpu_usage | float64 | 5,829 | 实例生命周期内 CPU 使用均值，百分比口径 |
| gpu_wrk_util | float64 | 0 | GPU 工作利用率观测值 |
| avg_mem | float64 | 1,217 | 平均内存使用，GB |
| max_mem | float64 | 0 | 最大内存使用，GB |
| avg_gpu_wrk_mem | float64 | 0 | 平均 GPU 显存使用，GB |
| max_gpu_wrk_mem | float64 | 0 | 最大 GPU 显存使用，GB |
| read | float64 | 3 | 生命周期内网络读取均值，字节 |
| write | float64 | 3 | 生命周期内网络写入均值，字节 |
| read_count | float64 | 3 | 读取次数均值 |
| write_count | float64 | 3 | 写入次数均值 |

指标口径风险：

- `gpu_wrk_util` 最大值 792，12,985 行大于 100，不能直接当作 0–100 的单卡百分比。
- 1,047,917 行 `gpu_wrk_util` 为 0，代表真实零使用还是采集缺失需要后续结合实例和任务状态判断。
- 官方说明这些值是实例生命周期内聚合值，不是逐秒时间序列。

## 6. `pai_group_tag_table`

- 行数：1,055,032
- 列数：5
- 文件大小：110.17 MB
- 全行重复：0
- 非空唯一 `inst_id`：1,055,032
- 非空唯一 `group`：316,956
- `inst_id + group` 与 `inst_id` 基数一致

| 字段 | 类型 | 缺失 | 业务含义 |
|---|---|---:|---|
| inst_id | string | 0 | 作业 ID |
| user | string | 1 | 用户标识 |
| gpu_type_spec | string | 1,034,399 | 指定的 GPU 类型；空值不表示没有 GPU |
| group | string | 0 | 相似输入/脚本/数据源的语义分组 |
| workload | string | 952,234 | 已识别的深度学习负载标签 |

`gpu_type_spec` 缺失 98.04%，`workload` 缺失 90.26%，只能作为可选标签，不能作为全量分析的主维度。

已知 workload 以 `bert`、`ctr`、`nmt`、`inception`、`graphlearn` 为主。

## 7. `pai_machine_spec`

- 行数：1,897
- 列数：5
- 文件大小：0.07 MB
- 全行重复：0
- `machine` 唯一且无缺失

| 字段 | 类型 | 缺失 | 业务含义 |
|---|---|---:|---|
| machine | string | 0 | 机器唯一标识 |
| gpu_type | string | 0 | GPU 类型；CPU 机器的值为 CPU |
| cap_cpu | float64 | 0 | CPU 核容量 |
| cap_mem | float64 | 0 | 内存容量，GB |
| cap_gpu | float64 | 0 | GPU 数量容量 |

容量分布：

- `cap_cpu`：64–96，均值 82.54。
- `cap_mem`：384–512 GB，均值 499.85 GB。
- `cap_gpu`：0–8，均值 3.55；83 台机器是 CPU-only。
- GPU 类型机器数：P100 798、T4 497、MISC 280、V100M32 135、V100 104、CPU 83。

该表可作为“真实历史机器规格”，但不能直接等同于用户在仿真中配置的虚拟服务器。

## 8. `pai_machine_metric`

- 行数：2,009,423
- 列数：12
- 文件大小：417.11 MB
- 全行重复：0
- 非空唯一 `worker_name`：2,009,421，存在 2 行 worker_name 重复
- 非空唯一 `machine`：1,720
- 全部 worker_name 均能在 instance 表中找到
- 只覆盖约 28.05% 的 instance worker_name

| 字段 | 类型 | 缺失 | 业务含义 |
|---|---|---:|---|
| worker_name | string | 0 | 实例标识 |
| machine | string | 0 | 机器标识 |
| start_time | float64 | 0 | 实例生命周期开始，相对秒 |
| end_time | float64 | 0 | 实例生命周期结束，相对秒 |
| machine_cpu_iowait | float64 | 1,090,518 | CPU I/O wait 机器级均值 |
| machine_cpu_kernel | float64 | 280,688 | CPU kernel 使用均值 |
| machine_cpu_usr | float64 | 232,095 | CPU user 使用均值 |
| machine_gpu | float64 | 241,494 | 机器级 GPU 指标 |
| machine_load_1 | float64 | 268,544 | 1 分钟负载均值 |
| machine_net_receive | float64 | 218,148 | 网络接收均值 |
| machine_num_worker | float64 | 295,258 | 机器上共置实例数均值 |
| machine_cpu | float64 | 1,125,895 | CPU 总体使用均值 |

GPU 指标口径检查：

- 1,044,545 行原始 `machine_gpu > 100`。
- 按 `machine_gpu / (100 × cap_gpu)` 归一化后，均值 0.2396。
- 仍有 1,593 行归一化后大于 1，1,522 行大于 1.05。
- 因此 `machine_gpu` 更像多卡机器上的汇总指标，但存在少量异常/尖峰，不能静默截断或删除。

## 9. 关联键摘要

| 左表 | 右表 | 关联键 | 实际关系 |
|---|---|---|---|
| job | task | job_name | 1:N |
| job | instance | job_name / inst_id | 1:N |
| task | instance | job_name + task_name | 1:N |
| instance | sensor | worker_name | 1:0..1 左右，传感器仅覆盖部分实例 |
| instance | machine_metric | worker_name | 1:0..1，指标仅覆盖部分实例 |
| machine_spec | instance | machine | 1:N |
| machine_spec | machine_metric | machine | 1:N |
| job | group_tag | inst_id | 近似 1:1，但存在覆盖差 |

更完整的关联覆盖率见 `docs/stage1_data_relationships.md`。
