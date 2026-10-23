# P0 技术基线

状态：`IN PROGRESS`  
分支：`goal/mvp`  
日期：2026-10-23

## 已冻结契约

- Rule DSL v0：[contracts/rule-dsl-v0.schema.json](contracts/rule-dsl-v0.schema.json)
- RecommendationFacts v0：[contracts/recommendation-facts-v0.schema.json](contracts/recommendation-facts-v0.schema.json)
- SourceAdapter v0：[contracts/source-adapter-v0.md](contracts/source-adapter-v0.md)
- 六项初始架构决策：[adr/README.md](adr/README.md)

## 工具链验证

| 项目 | 基线 |
|---|---|
| Python | 3.12 |
| 依赖与锁 | uv |
| API | FastAPI + Pydantic |
| ORM/迁移 | SQLAlchemy + Alembic |
| 数据库 | PostgreSQL 15+ |
| Web | React + TypeScript + Vite |
| 包管理 | pnpm |
| 后台任务 | PostgreSQL 持久化任务表 + 独立 Worker |

目标机器当前未安装 Docker，因此 P1 首先保证本机 PostgreSQL 可运行；容器化不作为首条纵向路径的前置条件。

## 行情供应商初步结论

P0 只冻结 `MarketDataProvider` 契约，不在领域模型中加入供应商字段。

首选技术验证对象：Tushare Pro。

依据：

- 官方日线接口说明包含 A 股开高低收、成交量和成交额，并明确交易日 15～16 点入库。
- 官方提供独立复权因子，可保存原始价和因子，避免只保存随查询终点变化的前复权结果。
- 官方提供交易日历与每日涨跌停价格，覆盖 v1 执行模型的基础需求。
- 权限受积分和流控限制，因此在确认账号权限前不能接受为正式运行依赖。

参考：

- [A 股日线行情](https://tushare.pro/document/1?doc_id=27)
- [复权因子](https://tushare.pro/document/2?doc_id=28)
- [交易日历](https://tushare.pro/document/2?doc_id=26)
- [每日涨跌停价格](https://tushare.pro/document/2?doc_id=183)

备选验证对象：BaoStock。其公开资料包含历史行情和复权说明，但正式采用前仍需验证更新时效、退市标的、交易状态、许可和稳定性。

结论：P1 显示“行情服务尚未配置”，不得用演示数据生成建议。P3 前必须完成真实账号的覆盖与时点验证。

## LLM 基线

- 供应商尚未冻结，业务代码只依赖 `LLMProvider` 端口。
- 所有任务使用版本化 JSON Schema。
- 提取任务必须返回原文起止位置和内容指纹。
- 格式重试与业务重试分开，禁止重试到结果“通过”为止。
- 真实模型比较在 P2 前使用固定文章集完成。

## P0 未完成项

- 选择 10～20 篇有合法使用方式的代表性真实文章，覆盖有效、模糊、重复、冲突和噪声。
- 建立一组包含 T+1、涨跌停、停牌和复权边界的固定行情夹具。
- 用真实 Tushare/BaoStock 账号验证覆盖、时间和许可。
- 对候选 LLM 完成证据定位、Schema、成本和延迟比较。
- 用非开发用户完成三个核心任务的原型测试。

这些事项没有完成前，P0 不能标记 `ACCEPTED`，文章研究阶段不得开始。

