# Portable Market Data v0

状态：`Draft for legacy inventory`

## 目的

旧电脑上的历史行情只作为一次性发现和导入来源。正式系统不得依赖旧电脑、旧数据库或旧抓取程序持续运行。

## 第一步：只读盘点

在旧电脑运行：

```bash
uv sync --all-groups
uv run ai-trader-data-inventory /path/to/export --output market-data-inventory.json
```

盘点工具支持 CSV 和 Parquet，只输出文件路径、大小、Schema、行数、证券数量、日期范围、校验和与缺失字段警告，不输出原始行情行。

如果旧数据仍在数据库中，先不要迁移整库。待确认数据库类型、表结构和字段含义后，再增加只读导出适配器。

## 正式导入最低要求

日线必须能映射到：

- `instrument_id`
- `trading_date`
- `open/high/low/close/previous_close`
- `volume/turnover`
- `trade_status/is_st`
- `available_at/availability_basis`
- `provider/source_revision/ingested_at`

同时提供交易日历、独立复权因子、数据来源说明和文件 SHA-256。只有前复权或后复权价格、但没有原始价和因子的旧数据不得作为正式回测基线。

## 导入状态

- `discovered`：只有盘点报告。
- `quarantined`：已复制，但字段、来源或时点尚未证明。
- `validated`：完成规范化和质量检查。
- `published`：生成不可变 Parquet 与校验和清单，可被回测引用。

只有 `published` 数据集可进入回测。原始文件、数据库转储和凭据不得提交到 Git。

