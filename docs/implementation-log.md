# 实施记录

## 2026-10-23：MVP 启动与首条工程切片

分支：`goal/mvp`  
状态：P0 `IN PROGRESS`，P1 Gate 尚未申请接受

### 已完成

- 建立 Python 3.12、FastAPI、SQLAlchemy、Alembic、React、TypeScript 和 Vite 工程骨架。
- 建立用户设置与不可变 `RiskPolicyVersion` 领域路径。
- 强制 `live_trading_enabled=false`，新规则确认策略默认开启。
- 建立 PostgreSQL 初始迁移、持久化任务表、租约队列和 Worker 心跳。
- 建立 LLM、行情、文章源和通知端口；未配置供应商时明确失败。
- 实现 4 步首次设置、三入口应用壳和真实空状态“今天”页。
- 行情和 AI 未配置时不生成模拟建议。
- 建立桌面、移动浏览器验收和 GitHub Actions CI。
- 冻结 Rule DSL v0、RecommendationFacts v0 与 SourceAdapter v0。

### 验证证据

- Python 单元与 API/队列集成测试：10 passed。
- Ruff：通过。
- Web 组件测试：2 passed。
- TypeScript：通过。
- Vite 生产构建：通过。
- Playwright Chromium：桌面和移动 2 passed，无横向溢出。
- PostgreSQL 初始迁移：upgrade → downgrade → upgrade 通过。
- 实际健康状态：数据库和 Worker 正常；行情与 AI 显示尚未配置。

### 验收中发现并修复

- PostgreSQL 在没有 ORM relationship 时先插入风险政策导致外键失败；现在显式先 flush 用户配置，并在 SQLite 测试中开启外键检查。
- 移动端 Playwright 设备描述默认选择 WebKit；现在固定使用 Chromium，保持单浏览器下载范围。
- Vitest 曾误收集 Playwright 测试；现在限定组件测试目录。

### 未完成与门禁

- P0 真实文章评测集、固定行情夹具、真实供应商和 LLM 比较未完成。
- 股票分析、文章学习和规则回测尚未开始，UI 中保持明确不可用状态。
- P1 仍需完成从全新环境的一键启动验证和正式恢复演练。
- 当前实现不能标记为可用 MVP，也未启用任何交易建议。

## 2026-10-26：免费行情与旧数据迁移基线

状态：P0 `IN PROGRESS`，免费来源尚未接受

### 已完成

- 用户数据策略改为免费来源优先；移除 Tushare Pro 作为首选依赖的决定。
- 冻结 `MarketDataProvider v0`，实现规范日线、交易日历、复权因子和可用时点模型。
- 实现 OHLC、唯一性、覆盖率、停牌成交、交易日历和未来信息质量门。
- 实现带 SHA-256 清单的不可变 Parquet 数据集写入器。
- 实现旧 CSV/Parquet 只读盘点工具，不输出原始行情行。
- 实现 BaoStock 未复权日线适配器和统计探针。

### 验证证据

- Python 单元与集成测试：20 passed；Ruff、Web 组件测试、TypeScript 和生产构建通过。
- 固定夹具、适配器、交叉对账和数据制品测试纳入 Python 测试集。
- BaoStock 首次探针返回 `10002007 网络接收错误`；失败被明确报告，没有写入数据集或伪造成功。
- 适配器增加 15 秒默认 socket 硬超时，重试后取得 116 条日线、58 个交易日、2 条基准复权因子，质量门通过。
- AKShare 同区间取得 116 条日线和 100% 覆盖，但因缺少独立复权因子被阻止单独发布。
- 两来源 116 条记录完全对齐：OHLC 无差异，成交额最大差 0.48 元，成交量最大差 50 股且在 AKShare 的 100 股精度内。

### 剩余事项

- 在另一网络和多次计划任务中验证 BaoStock 稳定性与硬超时。
- 旧电脑可访问后生成盘点清单；确定数据库类型前不实现猜测式数据库导入。
- 补齐停牌、退市、ST、复权边界和指数样本后才能接受行情来源。
