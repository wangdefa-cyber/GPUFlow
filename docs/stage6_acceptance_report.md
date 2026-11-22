# 阶段 6 验收报告

- 阶段：AI 辅助决策
- 日期：2026-11-22
- 结论：通过，可进入阶段 7

## 已完成

- [x] 规则引擎
- [x] 证据链结构
- [x] 建议持久化
- [x] 高等待规则
- [x] 受阻任务规则
- [x] 低 GPU 利用率规则
- [x] 高优先级饥饿规则
- [x] 低公平性规则
- [x] 同条件策略推荐
- [x] 健康状态 NO_ACTION
- [x] AI 决策页
- [x] 用户确认后采用调度预设
- [x] 容量建议不自动修改
- [x] 建议规则版本记录

## 尚未完成

- 外部大模型 API。
- 规则阈值可视化编辑。
- 容量建议自动草稿生成。
- 多数据版本对比建议。

## 验证

```text
pytest: 24 passed
AI page: rendered with persisted recommendations
Stage 6 smoke: generated LOW_GPU_UTILIZATION with 3 evidence records
```

## 主要交付

- `src/gpu_sim/advisor.py`
- `src/gpu_sim/advisor_service.py`
- `src/gpu_sim/models.py`
- `app_pages/ai_decision.py`
- `scripts/smoke_stage6.py`
- `tests/test_advisor.py`
- `docs/stage6_ai_advisory.md`

## 风险

| 风险 | 处理 |
|---|---|
| 固定阈值不一定适合所有场景 | 明确规则版本，后续支持配置 |
| 用户误解建议为自动决策 | 页面和文档均强调用户确认 |
| 历史任务无优先级 | 从任务快照读取，历史回放使用中性 5 |
| 容量建议不可自动执行 | 引导到 GPU 资源管理人工编辑 |
