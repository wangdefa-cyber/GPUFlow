# GPUFlow：GPU 资源管理与智能调度仿真系统

GPUFlow 基于阿里巴巴公开 `cluster-trace-gpu-v2020` GPU 集群追踪数据，目标是在后续阶段实现真实数据导入、虚拟 GPU 集群管理、任务调度、离散事件仿真、动态可视化、策略评价和 AI 辅助决策。

当前进度：**阶段 0–6 已完成，进入阶段 7（系统测试与最终交付）。**

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
## 阶段 4：最小可运行闭环

- `docs/stage4_closed_loop.md`：闭环实现、调度引擎、指标和验证说明
- `docs/stage4_acceptance_report.md`：阶段验收和遗留项
- `src/gpu_sim/`：SQLite、导入、调度、离散事件引擎和评价服务
- `artifacts/gpuflow.db`：本地 SQLite 数据库，不提交 Git
- `scripts/smoke_stage4.py`：真实历史样本与用户任务闭环冒烟测试

已实现：

- 真实历史 instance + task + job 样本导入
- 虚拟 GPU 服务器与用户任务持久化
- FIFO、SJF、Priority、First Fit、Best Fit
- GPU/CPU/内存/型号多资源约束
- 确定性离散事件仿真
- 事件、任务结果、指标与资源采样持久化
- 动态时间线、甘特图和实验回看
## 阶段 5：算法与仿真完善

- `docs/stage5_algorithm_refinement.md`：步进控制、批量实验和对比结果
- `docs/stage5_acceptance_report.md`：阶段验收与剩余风险
- 可步进引擎：开始、继续、暂停、单步、运行到结束、重置
- 四策略同条件批量实验
- 多策略指标表、柱状图、GPU 利用率曲线和完成时间分布
- 输入兼容性和结果哈希校验
## 阶段 6：AI 辅助决策

- `docs/stage6_ai_advisory.md`：规则目录、证据结构和用户确认边界
- `docs/stage6_acceptance_report.md`：阶段验收
- `src/gpu_sim/advisor.py`：纯规则引擎
- `src/gpu_sim/advisor_service.py`：建议生成、持久化和采用
- AI 决策页支持证据表、配置补丁和调度预设采用
- 容量类建议只展示候选补丁，不自动修改资源配置
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

- Web 原型、SQLite、调度算法、最小闭环、实时步进、策略批量对比和规则化 AI 建议均已实现。
- 历史数据中的缺失值、状态差异、部分采样和指标口径已记录，不得无提示删除或伪造。
- 真实历史数据、系统配置数据和仿真生成数据必须保持可区分。
- 原始 CSV/TAR 不纳入 Git。
