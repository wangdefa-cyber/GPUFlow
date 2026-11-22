# GPU 资源管理与智能调度仿真系统

本项目基于阿里巴巴公开的 `cluster-trace-gpu-v2020` GPU 集群追踪数据，目标是在后续阶段实现资源管理、任务调度、离散事件仿真、动态可视化和策略评价的一体化 Web 系统。

当前进度：**阶段 0（环境与项目审计）和阶段 1（数据集研究）已完成，等待确认后进入阶段 2。**

## 当前交付物

- `docs/project_brief.md`：项目原始需求。
- `docs/reference/alibaba_gpu_trace_readme.md`：官方数据说明快照。
- `docs/stage0_environment_audit.md`：环境与项目审计报告。
- `docs/stage1_data_dictionary.md`：七张表的数据字典。
- `docs/stage1_data_audit_report.md`：数据规模、质量与导入方案。
- `docs/stage1_data_relationships.md`：表间关系和关联完整性。
- `docs/stage1_database_recommendations.md`：数据库与业务模型建议。
- `reports/data_audit.json`：完整机器可读审计结果。
- `reports/data_profile_summary.csv`：表级摘要。
- `reports/data_relationships.json`：键覆盖率审计结果。
- `reports/data_quality_checks.json`：状态完整性与 GPU 指标口径检查。

## 环境

```powershell
conda env create -f environment.yml
conda activate gpu_analysis
```

已在本机创建的环境为 `D:\anaconda3\envs\gpu_analysis`。

## 复现数据审计

```powershell
conda run -n gpu_analysis python scripts\audit_gpu_trace.py --chunksize 200000
conda run -n gpu_analysis python scripts\audit_relations.py
conda run -n gpu_analysis python scripts\audit_quality.py
```

原始数据体积较大，`data/` 中的 CSV 和 TAR 文件不纳入 Git。审计脚本使用分块读取和流式 SHA-256，不会一次性加载整张表。

## 当前边界

- 尚未开始系统分析、架构实现、数据库建表、调度算法或 Web 页面开发。
- 历史监控指标只表示采集期内的观测值，不能直接作为未来仿真结果。
- 仿真生成的资源状态、任务时间和利用指标将在后续阶段明确标记为仿真数据。
