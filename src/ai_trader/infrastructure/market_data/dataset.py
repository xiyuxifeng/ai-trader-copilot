import json
import os
import shutil
import tempfile
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

import polars as pl

from ai_trader.application.market_data_quality import validate_daily_bars
from ai_trader.domain.market_data import AdjustmentFactor, DailyBar, TradeCalendarDay


@dataclass(frozen=True, slots=True)
class DatasetFile:
    path: str
    rows: int
    sha256: str


@dataclass(frozen=True, slots=True)
class MarketDatasetManifest:
    schema_version: str
    dataset_id: str
    created_at: str
    provider: str
    source_revisions: tuple[str, ...]
    instruments: tuple[str, ...]
    start_date: str
    end_date: str
    quality_accepted: bool
    files: tuple[DatasetFile, ...]


class MarketDatasetWriter:
    def write(
        self,
        *,
        target_root: Path,
        bars: tuple[DailyBar, ...],
        calendar: tuple[TradeCalendarDay, ...],
        factors: tuple[AdjustmentFactor, ...],
    ) -> MarketDatasetManifest:
        quality = validate_daily_bars(bars, calendar, factors)
        if not quality.accepted:
            raise ValueError("未通过质量门的行情不能写入正式数据集")
        if not bars:
            raise ValueError("行情数据集不能为空")
        if not calendar:
            raise ValueError("正式行情数据集必须包含交易日历")

        dataset_id = f"daily-{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{uuid4().hex[:8]}"
        target_root.mkdir(parents=True, exist_ok=True)
        final_dir = target_root / dataset_id
        temporary_dir = Path(tempfile.mkdtemp(prefix=f".{dataset_id}-", dir=target_root))
        try:
            files = (
                self._write_frame(temporary_dir, "daily_bars.parquet", _bar_rows(bars)),
                self._write_frame(
                    temporary_dir, "trade_calendar.parquet", _calendar_rows(calendar)
                ),
                self._write_frame(
                    temporary_dir, "adjustment_factors.parquet", _factor_rows(factors)
                ),
                self._write_json(
                    temporary_dir,
                    "quality_report.json",
                    _json_safe(asdict(quality)),
                    rows=len(quality.issues),
                ),
            )
            manifest = MarketDatasetManifest(
                schema_version="market-dataset-v0",
                dataset_id=dataset_id,
                created_at=datetime.now(UTC).isoformat(),
                provider=bars[0].provider,
                source_revisions=tuple(sorted({bar.source_revision for bar in bars})),
                instruments=tuple(sorted({bar.instrument_id for bar in bars})),
                start_date=min(bar.trading_date for bar in bars).isoformat(),
                end_date=max(bar.trading_date for bar in bars).isoformat(),
                quality_accepted=True,
                files=files,
            )
            (temporary_dir / "manifest.json").write_text(
                json.dumps(asdict(manifest), ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            os.replace(temporary_dir, final_dir)
            return manifest
        except Exception:
            shutil.rmtree(temporary_dir, ignore_errors=True)
            raise

    @staticmethod
    def _write_frame(directory: Path, filename: str, rows: list[dict[str, object]]) -> DatasetFile:
        path = directory / filename
        pl.DataFrame(rows).write_parquet(path, compression="zstd", statistics=True)
        return DatasetFile(path=filename, rows=len(rows), sha256=_file_sha256(path))

    @staticmethod
    def _write_json(
        directory: Path, filename: str, payload: object, *, rows: int
    ) -> DatasetFile:
        path = directory / filename
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return DatasetFile(path=filename, rows=rows, sha256=_file_sha256(path))


def _bar_rows(bars: tuple[DailyBar, ...]) -> list[dict[str, object]]:
    return [
        {
            "instrument_id": bar.instrument_id,
            "trading_date": bar.trading_date,
            "open": bar.open,
            "high": bar.high,
            "low": bar.low,
            "close": bar.close,
            "previous_close": bar.previous_close,
            "volume": bar.volume,
            "volume_unit": bar.volume_unit.value,
            "volume_resolution": bar.volume_resolution,
            "turnover": bar.turnover,
            "trade_status": bar.trade_status.value,
            "is_st": bar.is_st,
            "available_at": bar.available_at,
            "availability_basis": bar.availability_basis.value,
            "provider": bar.provider,
            "source_revision": bar.source_revision,
            "ingested_at": bar.ingested_at,
        }
        for bar in bars
    ]


def _calendar_rows(rows: tuple[TradeCalendarDay, ...]) -> list[dict[str, object]]:
    return [
        {
            "calendar_date": row.calendar_date,
            "is_trading_day": row.is_trading_day,
            "provider": row.provider,
            "ingested_at": row.ingested_at,
        }
        for row in rows
    ]


def _factor_rows(rows: tuple[AdjustmentFactor, ...]) -> list[dict[str, object]]:
    return [
        {
            "instrument_id": row.instrument_id,
            "effective_date": row.effective_date,
            "forward_factor": row.forward_factor,
            "backward_factor": row.backward_factor,
            "raw_factor": row.raw_factor,
            "provider": row.provider,
            "source_revision": row.source_revision,
            "ingested_at": row.ingested_at,
        }
        for row in rows
    ]


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_safe(value: object) -> object:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value
