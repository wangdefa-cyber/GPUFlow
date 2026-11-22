# 阶段 0：环境与项目审计报告

- 审计日期：2026-11-22
- 审计范围：当前项目目录、数据文件、Python/Conda 环境、Git、已安装 Skill
- 结论：阶段 0 已通过；可以进入阶段 1 的数据研究

## 1. 项目目录审计

审计开始时，项目根目录仅包含 `data/`。当时没有 Git 仓库、应用代码、数据库、测试或设计文档。

项目根目录：`C:\Users\Auraro\Desktop\信息系统与设计`

七张官方数据表均已下载并解压。另外保留了七个 `.tar` 原始归档。原始 CSV 合计约 3.65 GB。

## 2. 开发环境

| 项目 | 结果 |
|---|---|
| 操作系统 | Windows 10 10.0.19045 |
| Conda | 23.7.4 |
| Conda 安装目录 | `D:\anaconda3` |
| 环境名称 | `gpu_analysis` |
| 环境目录 | `D:\anaconda3\envs\gpu_analysis` |
| Python | 3.11.18 |
| Git | 2.54.0.windows.1 |
| 可用磁盘 C | 30.46 GB |
| 可用磁盘 D | 43.79 GB |

已安装的核心依赖：

| 依赖 | 验证版本 |
|---|---:|
| pandas | 3.1.1 |
| numpy | 2.4.6 |
| SQLAlchemy | 2.1.9 |
| pytest | 9.2.0 |
| plotly | 7.1.0 |
| streamlit | 1.67.0 |

`environment.yml` 已加入项目根目录，可用于在新环境中复现。

## 3. 数据文件审计

| 表 | CSV 大小 | 物理行数 | 已解压 | TAR 保留 |
|---|---:|---:|---|---|
| pai_job_table | 127.11 MB | 1,055,501 | 是 | 是 |
| pai_task_table | 108.15 MB | 1,261,050 | 是 | 是 |
| pai_instance_table | 1,883.68 MB | 7,522,002 | 是 | 是 |
| pai_sensor_table | 1,007.94 MB | 3,033,232 | 是 | 是 |
| pai_group_tag_table | 110.17 MB | 1,055,032 | 是 | 是 |
| pai_machine_spec | 0.07 MB | 1,897 | 是 | 是 |
| pai_machine_metric | 417.11 MB | 2,009,423 | 是 | 是 |

七张 CSV 的 SHA-256 均与官方 README 公布的校验值一致。

## 4. Skill 与工具审计

当前可用且与本项目直接相关的全局 Skill：

- `developing-with-streamlit`
- `codebase-design`
- `domain-driven-design`
- `vertical-slice-architecture`
- `service-boundaries`
- `event-driven-systems`
- `persistence-design`
- `event-sourcing`
- `design-review`

项目级 Streamlit Skill 已按用户要求移除，只保留全局版本。

## 5. Git 与项目规划

已执行 `git init`。`.gitignore` 已排除大体积原始数据、数据库、缓存、密钥和生成产物。

后续代码目录规划建议：

```text
app/                 Streamlit 页面与导航
src/gpu_sim/
  data/              数据导入、清洗与审计
  resources/         服务器与资源模型
  scheduling/        FIFO、SJF、优先级、Best Fit
  simulation/        离散事件仿真引擎
  analytics/         指标计算与策略对比
  ai/                可追溯的规则建议层
tests/               数据、业务、算法、系统测试
config/              可版本化配置
docs/                阶段文档、ADR、数据字典
scripts/             可复现的数据和运维脚本
reports/             审计与实验报告
data/                原始数据，不提交 Git
artifacts/           仿真输出，不提交 Git
```

## 6. 风险与约束

1. 原始数据约 3.65 GB，开发机 C 盘剩余约 30 GB。数据库和仿真产物应避免无区分地复制全部 CSV。
2. SQLite 适合课程项目和单机运行，但大表查询必须建立索引、限制结果集，并优先使用预聚合表。
3. 时间字段是脱敏后的相对秒数，不是可直接解释为真实日期的 Unix 时间。
4. CPU、GPU 计划量以百分比表示；进入资源模型前必须明确除以 100 转换为核数/GPU 当量。
5. Conda 版本较旧，但不影响当前环境复现；暂不升级，避免引入环境变动。

## 7. 阶段 0 验收

- [x] 项目目录已检查
- [x] 七张数据表存在并解压
- [x] 官方数据说明已读取并保存
- [x] Python 环境已创建
- [x] 核心依赖已安装并验证
- [x] 相关 Skill 已检查
- [x] Git 已初始化
- [x] 大文件已从 Git 忽略
- [x] 项目目录规划已明确
