# 阶段 4 验收报告

- 阶段：最小可运行闭环
- 日期：2026-11-22
- 结论：通过，可进入阶段 5

## 已完成

- [x] SQLite 数据库持久化
- [x] 虚拟服务器 CRUD
- [x] 用户任务 CRUD
- [x] 真实历史实例/任务/用户关联导入
- [x] FIFO、SJF、Priority 排序
- [x] First Fit、Best Fit 放置
- [x] GPU、CPU、内存和 GPU 型号约束
- [x] 离散事件仿真
- [x] 资源释放
- [x] 事件与任务结果持久化
- [x] 资源利用率采样
- [x] 九项评价指标
- [x] 动态时间线
- [x] Plotly 甘特图
- [x] 历史实验回看

## 尚未完成

- 暂停、继续、单步、重置的交互控制。
- 策略批量对比页面。
- 历史分层抽样和覆盖率优化。
- 任务取消和失败注入。
- AI 规则引擎。

## 验证

```text
pytest: 18 passed
Streamlit AppTest: 9/9 pages
Streamlit Agent API: ready, 0 exceptions
History import smoke: 20 real tasks
User closed loop smoke: 6 tasks, 100% completion
```

## 主要交付物

- `src/gpu_sim/domain.py`
- `src/gpu_sim/models.py`
- `src/gpu_sim/db.py`
- `src/gpu_sim/importer.py`
- `src/gpu_sim/scheduling.py`
- `src/gpu_sim/simulation.py`
- `src/gpu_sim/application.py`
- `src/gpu_sim/services.py`
- `app_pages/data_center.py`
- `app_pages/resources.py`
- `app_pages/tasks.py`
- `app_pages/scheduler.py`
- `app_pages/simulation.py`
- `scripts/smoke_stage4.py`
- `tests/test_simulation_engine.py`
- `tests/test_database_flow.py`
- `docs/stage4_closed_loop.md`

## 风险

| 风险 | 处理 |
|---|---|
| SQLite 文件位于 `artifacts/`，不提交 Git | README 给出路径和启动方式 |
| 历史样本是文件前部有界样本 | 页面和文档持续标注，阶段 5 改进抽样 |
| 历史优先级缺失 | 统一中性值 5 并写入元数据 |
| GPU 利用率可能很低 | 同时展示分配量和容量，避免只看百分比 |
| 当前无交互暂停/单步 | 列为阶段 5 目标，不冒充已实现 |
