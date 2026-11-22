# GPUFlow：GPU 资源管理与智能调度仿真系统

GPUFlow 基于阿里巴巴公开 `cluster-trace-gpu-v2020` GPU 集群追踪数据，目标是在后续阶段实现真实数据导入、虚拟 GPU 集群管理、任务调度、离散事件仿真、动态可视化、策略评价和 AI 辅助决策。

当前进度：**阶段 0、1、2 已完成，等待确认后进入阶段 3（可操作原型）。**

## 阶段 0：环境与项目审计

- `docs/stage0_environment_audit.md`
- `docs/reference/alibaba_gpu_trace_readme.md`
- `environment.yml`

## 阶段 1：数据集研究

- `docs/stage1_data_dictionary.md`
- `docs/stage1_data_audit_report.md`
- `docs/stage1_data_relationships.md`
- `docs/stage1_database_recommendations.md`
- `reports/data_audit.json`
- `reports/data_profile_summary.csv`
- `reports/data_relationships.json`
- `reports/data_quality_checks.json`

## 阶段 2：系统分析与设计

- `docs/stage2_requirements_analysis.md`：角色、用例、业务流程图、功能和非功能需求
- `docs/stage2_system_design.md`：模块化单体架构、模块边界、调度与仿真设计
- `docs/stage2_database_design.md`：历史/配置/仿真 ER 图和表设计
- `docs/stage2_module_interfaces.md`：接口契约、依赖规则和测试面
- `docs/stage2_metrics_definitions.md`：评价指标、公式和比较规则
- `docs/glossary.md`：统一领域术语
- `docs/adr/`：关键架构决策记录
- `docs/stage2_acceptance_report.md`：阶段验收、未完成项和风险

## 环境

```powershell
conda env create -f environment.yml
conda activate gpu_analysis
```

本机已验证环境：`D:\anaconda3\envs\gpu_analysis`

核心版本：Python 3.11.18、pandas 3.1.1、SQLAlchemy 2.1.9、pytest 9.2.0、plotly 7.1.0、streamlit 1.67.0。

## 复现数据审计

```powershell
conda run -n gpu_analysis python scripts\audit_gpu_trace.py --chunksize 200000
conda run -n gpu_analysis python scripts\audit_relations.py
conda run -n gpu_analysis python scripts\audit_quality.py
```

## 当前边界

- 尚未实现数据库、调度算法、仿真引擎或 Web 页面。
- 历史数据中的缺失值、状态差异、部分采样和指标口径已记录，不得无提示删除或伪造。
- 真实历史数据、系统配置数据和仿真生成数据必须保持可区分。
- 原始 CSV/TAR 不纳入 Git。
