# GPUFlow：GPU 资源管理与智能调度仿真系统

GPUFlow v1.0 是一个基于阿里巴巴公开 `cluster-trace-gpu-v2020` GPU 集群追踪数据的本地 Web 系统，覆盖真实数据审计、虚拟 GPU 集群配置、任务管理、调度实验、离散事件仿真、动态可视化、策略对比、评价指标和证据化 AI 建议。

当前状态：**所有阶段 0–7 已完成，最终验收通过。**

## 快速启动

双击项目根目录的：

```text
start_gpuflow.bat
```

脚本会自动激活 `gpu_analysis` 环境并启动 GPUFlow。

也可以在 PowerShell 中手动启动：

```powershell
conda activate gpu_analysis
cd C:\Users\Auraro\Desktop\信息系统与设计
streamlit run streamlit_app.py
```

默认访问：`http://localhost:8501`

数据库首次启动自动创建：`artifacts/gpuflow.db`

## 核心能力

- 七张阿里巴巴 GPU Trace 表校验、审计和有限预览
- 真实历史 instance + task + job 样本导入
- 虚拟 GPU 服务器与用户任务持久化
- FIFO、SJF、Priority 排序
- First Fit、Best Fit 放置
- GPU、CPU、内存和 GPU 型号约束
- 确定性离散事件仿真
- 开始、继续、暂停、单步、运行到结束和重置
- 动态资源时间线、Plotly 甘特图和事件日志
- 四策略同条件批量实验
- 指标表、柱状图、利用率曲线和完成时间分布
- 规则化 AI 建议、证据链和用户确认采用
- SQLite 持久化、结果哈希和实验回看

## 文档入口

### 最终交付

- `docs/user_guide.md`：用户使用说明
- `docs/stage7_test_report.md`：最终测试与性能报告
- `docs/stage7_acceptance_report.md`：最终验收报告
- `docs/demo_guide.md`：10 分钟演示流程和幻灯片结构
- `docs/glossary.md`：领域术语表
- `docs/adr/`：架构决策记录

### 阶段文档

- `docs/stage0_environment_audit.md`
- `docs/stage1_data_dictionary.md`
- `docs/stage1_data_audit_report.md`
- `docs/stage1_data_relationships.md`
- `docs/stage1_database_recommendations.md`
- `docs/stage2_requirements_analysis.md`
- `docs/stage2_system_design.md`
- `docs/stage2_database_design.md`
- `docs/stage2_module_interfaces.md`
- `docs/stage2_metrics_definitions.md`
- `docs/stage3_prototype_design.md`
- `docs/stage4_closed_loop.md`
- `docs/stage5_algorithm_refinement.md`
- `docs/stage6_ai_advisory.md`

## 代码结构

```text
streamlit_app.py              Streamlit 入口和导航
app_pages/                    九个业务页面
src/gpu_sim/
  domain.py                   资源向量和仿真结果契约
  models.py                   SQLAlchemy 模型
  db.py                       SQLite 生命周期
  importer.py                 真实历史样本导入
  scheduling.py               排序和放置算法
  simulation.py               确定性离散事件引擎
  services.py                 持久化与查询服务
  application.py              单次/实时/批量实验编排
  advisor.py                  证据化规则引擎
  advisor_service.py          AI 建议持久化和采用
  prototype/                  页面共享原型组件
tests/                        自动化测试
scripts/                      审计、冒烟、性能和最终验收脚本
docs/                         阶段文档、报告和演示材料
reports/                      数据审计 JSON/CSV
data/                         原始数据，不提交 Git
artifacts/                    SQLite 与临时运行产物，不提交 Git
```

## 环境

```powershell
conda env create -f environment.yml
conda activate gpu_analysis
```

已验证版本：

- Python 3.11.18
- pandas 3.1.1
- NumPy 2.4.6
- SQLAlchemy 2.1.9
- pytest 9.2.0
- Plotly 7.1.0
- Streamlit 1.67.0

## 验证命令

```powershell
conda run -n gpu_analysis pytest -q
conda run -n gpu_analysis python scripts\smoke_stage5.py
conda run -n gpu_analysis python scripts\smoke_stage6.py
conda run -n gpu_analysis python scripts\performance_check.py
conda run -n gpu_analysis python scripts\final_acceptance.py
```

当前验证结果：

- 自动化测试：**26 passed**
- Streamlit：**9/9 页面无异常**
- Agent API：`ready`，无页面异常
- 最终端到端验收：**PASS**
- 1,000 任务仿真：约 **1.9–2.1 秒**，峰值内存低于 **8 MB**

## 数据真实性

系统始终区分：

- 真实历史数据：阿里巴巴 GPU Trace，只读。
- 系统配置数据：虚拟服务器、用户任务和调度参数。
- 仿真生成数据：任务分配、事件、资源采样和指标。
- AI 建议：基于证据生成的候选行动。

历史监控值不会被冒充为仿真结果。原始 CSV/TAR 不纳入 Git。

## 已知限制

- 历史导入为有界文件前部终止实例样本，尚未实现分层抽样。
- GPU 型号严格匹配。
- 未实现 backfill、抢占和资源预留。
- 公平性首版按用户计算 Jain 指数。
- AI 使用固定阈值规则，尚未接入外部大模型。
