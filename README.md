# GPUFlow：GPU 资源管理与智能调度仿真系统

GPUFlow 基于阿里巴巴公开 `cluster-trace-gpu-v2020` GPU 集群追踪数据，目标是在后续阶段实现真实数据导入、虚拟 GPU 集群管理、任务调度、离散事件仿真、动态可视化、策略评价和 AI 辅助决策。

当前进度：**阶段 0–3 已完成，等待确认后进入阶段 4（最小可运行闭环）。**

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

## 阶段 3：可操作 Web 原型

- `streamlit_app.py`：九页面 Streamlit 原型入口
- `docs/stage3_prototype_design.md`：信息架构、页面设计和交互规范
- `docs/stage3_acceptance_report.md`：原型验收结果和阶段 4 顺序
- `.streamlit/config.toml`：深色科技风主题
- `src/gpu_sim/prototype/`：原型规则、会话状态和真实数据只读访问
- `app_pages/`：总览、数据中心、资源、任务、调度、仿真、对比、AI、设置
- `tests/`：原型逻辑和九页面渲染测试

启动原型：

```powershell
conda activate gpu_analysis
streamlit run streamlit_app.py
```
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

- Web 原型已实现；SQLite 持久化、调度算法和离散事件仿真引擎仍待阶段 4。
- 历史数据中的缺失值、状态差异、部分采样和指标口径已记录，不得无提示删除或伪造。
- 真实历史数据、系统配置数据和仿真生成数据必须保持可区分。
- 原始 CSV/TAR 不纳入 Git。
