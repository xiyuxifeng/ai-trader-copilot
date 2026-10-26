import argparse
import json
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path

import polars as pl


@dataclass(frozen=True, slots=True)
class InventoryFile:
    path: str
    format: str
    bytes: int
    sha256: str
    rows: int | None
    columns: tuple[str, ...]
    symbol_column: str | None
    symbol_count: int | None
    date_column: str | None
    minimum_date: str | None
    maximum_date: str | None
    warnings: tuple[str, ...]
    error: str | None = None


@dataclass(frozen=True, slots=True)
class InventoryReport:
    schema_version: str
    source_root: str
    file_count: int
    total_bytes: int
    files: tuple[InventoryFile, ...]
    unsupported_files: int


_SYMBOL_COLUMNS = ("instrument_id", "symbol", "code", "ts_code")
_DATE_COLUMNS = ("trading_date", "trade_date", "date")
_PRICE_GROUPS = (("open",), ("high",), ("low",), ("close",), ("volume", "vol"))


def inspect_market_data(source: Path) -> InventoryReport:
    source = source.expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(f"数据路径不存在：{source}")
    candidates = [source] if source.is_file() else sorted(source.rglob("*"))
    supported = [path for path in candidates if path.suffix.lower() in {".csv", ".parquet"}]
    unsupported = sum(1 for path in candidates if path.is_file() and path not in supported)
    root = source if source.is_dir() else source.parent
    files = tuple(_inspect_file(path, root) for path in supported)
    return InventoryReport(
        schema_version="market-data-inventory-v0",
        source_root=str(source),
        file_count=len(files),
        total_bytes=sum(item.bytes for item in files),
        files=files,
        unsupported_files=unsupported,
    )


def _inspect_file(path: Path, root: Path) -> InventoryFile:
    relative = str(path.relative_to(root))
    size = path.stat().st_size
    checksum = _file_sha256(path)
    file_format = path.suffix.lower().removeprefix(".")
    try:
        frame = (
            pl.scan_csv(path, infer_schema_length=10_000)
            if file_format == "csv"
            else pl.scan_parquet(path)
        )
        columns = tuple(frame.collect_schema().names())
        symbol_column = _first_present(columns, _SYMBOL_COLUMNS)
        date_column = _first_present(columns, _DATE_COLUMNS)
        expressions = [pl.len().alias("row_count")]
        if symbol_column:
            expressions.append(pl.col(symbol_column).n_unique().alias("symbol_count"))
        if date_column:
            expressions.extend(
                (
                    pl.col(date_column).cast(pl.String).min().alias("minimum_date"),
                    pl.col(date_column).cast(pl.String).max().alias("maximum_date"),
                )
            )
        summary = frame.select(expressions).collect().row(0, named=True)
        return InventoryFile(
            path=relative,
            format=file_format,
            bytes=size,
            sha256=checksum,
            rows=int(summary["row_count"]),
            columns=columns,
            symbol_column=symbol_column,
            symbol_count=(int(summary["symbol_count"]) if symbol_column else None),
            date_column=date_column,
            minimum_date=(str(summary["minimum_date"]) if date_column else None),
            maximum_date=(str(summary["maximum_date"]) if date_column else None),
            warnings=_schema_warnings(columns, symbol_column, date_column),
        )
    except Exception as error:
        return InventoryFile(
            path=relative,
            format=file_format,
            bytes=size,
            sha256=checksum,
            rows=None,
            columns=(),
            symbol_column=None,
            symbol_count=None,
            date_column=None,
            minimum_date=None,
            maximum_date=None,
            warnings=("文件无法完成结构盘点，不能直接导入",),
            error=str(error),
        )


def _schema_warnings(
    columns: tuple[str, ...], symbol_column: str | None, date_column: str | None
) -> tuple[str, ...]:
    normalized = {column.lower() for column in columns}
    warnings = []
    if symbol_column is None:
        warnings.append("未识别证券代码列")
    if date_column is None:
        warnings.append("未识别交易日期列")
    for aliases in _PRICE_GROUPS:
        if not normalized.intersection(aliases):
            warnings.append(f"未识别 {aliases[0]} 列")
    if not normalized.intersection({"adjustment_factor", "adj_factor", "adjustflag"}):
        warnings.append("未识别复权字段或复权因子")
    if not normalized.intersection({"trade_status", "tradestatus", "suspended"}):
        warnings.append("未识别交易状态字段")
    return tuple(warnings)


def _first_present(columns: tuple[str, ...], aliases: tuple[str, ...]) -> str | None:
    by_lower = {column.lower(): column for column in columns}
    return next((by_lower[alias] for alias in aliases if alias in by_lower), None)


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="只读盘点旧行情 CSV/Parquet，不导出原始数据")
    parser.add_argument("source", type=Path, help="旧行情文件或目录")
    parser.add_argument("--output", type=Path, help="清单 JSON 输出路径；省略时输出到终端")
    args = parser.parse_args()
    report = inspect_market_data(args.source)
    payload = json.dumps(asdict(report), ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")


if __name__ == "__main__":
    main()
