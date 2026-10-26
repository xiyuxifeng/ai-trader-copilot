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

用户约束：v1 不使用要求付费订阅、积分购买或付费权限的数据源。Tushare Pro 不再作为首选实现依赖。

候选来源：

- BaoStock：官方资料提供历史 A 股 K 线、交易日历和复权因子；已实现只取未复权日线并独立保存复权因子的适配器。
- AKShare：作为第二候选和交叉对账来源；其官方项目明确是开源财经数据接口，但上游网页接口和口径仍需逐项验证。
- 旧电脑历史数据：只走一次性盘点、隔离、规范化和校验流程，不作为运行依赖。

2026-10-26 首次真实 BaoStock 探针访问两只股票 2024 年一季度样本时曾返回 `10002007 网络接收错误`，暴露出免费 socket 服务的稳定性风险。适配器随后增加 15 秒默认硬超时；重试成功取得 116 条日线、58 个交易日和区间开始前生效的复权因子，质量检查通过。

同区间 AKShare 取得相同 116 条日线和 100% 覆盖，但没有独立复权因子，因此不能单独发布为正式数据集。交叉对账结果：116 条记录日期完全重合，OHLC 无差异，成交额最大差 0.48 元；AKShare 成交量按手提供，换算后相对 BaoStock 最多相差 50 股，在其 100 股数据精度内。

当前结论：BaoStock 是主数据候选，AKShare 是日线交叉校验候选。两者仍需扩大到停牌、ST、退市、复权事件、指数和不同市场时期后才能正式接受。

参考：[BaoStock 官方站点](https://www.baostock.com/)、[AKShare 官方仓库](https://github.com/akfamily/akshare)

结论：产品继续显示“行情服务尚未配置”，不得用演示数据生成建议。当前小样成功不等于正式供应商验收。

## LLM 基线

- 供应商尚未冻结，业务代码只依赖 `LLMProvider` 端口。
- 所有任务使用版本化 JSON Schema。
- 提取任务必须返回原文起止位置和内容指纹。
- 格式重试与业务重试分开，禁止重试到结果“通过”为止。
- 真实模型比较在 P2 前使用固定文章集完成。

## P0 未完成项

- 选择 10～20 篇有合法使用方式的代表性真实文章，覆盖有效、模糊、重复、冲突和噪声。
- 建立一组包含 T+1、涨跌停、停牌和复权边界的固定行情夹具。
- 用 BaoStock/AKShare 免费来源验证覆盖、时间、许可和稳定性。
- 对候选 LLM 完成证据定位、Schema、成本和延迟比较。
- 用非开发用户完成三个核心任务的原型测试。

这些事项没有完成前，P0 不能标记 `ACCEPTED`，文章研究阶段不得开始。
