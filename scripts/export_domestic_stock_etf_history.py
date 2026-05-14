from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

import yfinance as yf
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server.db import SessionLocal  # noqa: E402
from server.models import Instrument  # noqa: E402
from server.services.price_fetcher import normalize_code, normalize_exchange  # noqa: E402


@dataclass(frozen=True)
class Target:
    instrument_id: int
    name: str
    type: str
    code: str
    exchange: str | None
    currency: str
    ticker: str


def infer_exchange(code: str, exchange: str | None) -> str | None:
    normalized_exchange = normalize_exchange(exchange)
    if normalized_exchange in {"SH", "SZ", "BJ"}:
        return normalized_exchange
    if code.startswith(("5", "6", "9")):
        return "SH"
    if code.startswith(("0", "1", "2", "3")):
        return "SZ"
    if code.startswith(("4", "8", "92")):
        return "BJ"
    return normalized_exchange


def yahoo_ticker(code: str, exchange: str | None) -> str | None:
    if exchange == "SH":
        return f"{code}.SS"
    if exchange == "SZ":
        return f"{code}.SZ"
    # Yahoo Finance usually has poor/no Beijing Stock Exchange coverage.
    return None


def load_targets(include_gold: bool) -> list[Target]:
    types = ["stock", "etf"] + (["gold"] if include_gold else [])
    with SessionLocal() as db:
        instruments = db.scalars(
            select(Instrument)
            .where(Instrument.is_active == True, Instrument.type.in_(types))
            .order_by(Instrument.id)
        ).all()

    targets: list[Target] = []
    for inst in instruments:
        code = normalize_code(inst.code)
        if not code or not code.isdigit() or len(code) != 6:
            continue
        exchange = infer_exchange(code, inst.exchange)
        ticker = yahoo_ticker(code, exchange)
        if not ticker:
            continue
        targets.append(
            Target(
                instrument_id=inst.id,
                name=inst.name,
                type=inst.type,
                code=code,
                exchange=exchange,
                currency=inst.currency,
                ticker=ticker,
            )
        )
    return targets


def read_done_tickers(done_path: Path) -> set[str]:
    if not done_path.exists():
        return set()
    done: set[str] = set()
    with done_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    done.add(json.loads(line)["ticker"])
                except Exception:
                    continue
    return done


def append_done(done_path: Path, target: Target, rows: int, status: str, error: str | None = None) -> None:
    payload = {
        "ticker": target.ticker,
        "instrument_id": target.instrument_id,
        "code": target.code,
        "exchange": target.exchange,
        "rows": rows,
        "status": status,
        "error": error,
        "finished_at": datetime.now().isoformat(timespec="seconds"),
    }
    with done_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def ensure_csv_header(csv_path: Path) -> None:
    if csv_path.exists() and csv_path.stat().st_size > 0:
        return
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow([
            "instrument_id",
            "name",
            "type",
            "code",
            "exchange",
            "currency",
            "ticker",
            "date",
            "close",
            "source",
        ])


def export_one(target: Target, csv_path: Path) -> int:
    hist = yf.Ticker(target.ticker).history(period="max", auto_adjust=False)
    if hist is None or hist.empty or "Close" not in hist:
        return 0
    rows = []
    for index, row in hist.iterrows():
        close = row.get("Close")
        if close is None:
            continue
        try:
            close_float = float(close)
        except Exception:
            continue
        if close_float <= 0:
            continue
        date_value = index.date().isoformat() if hasattr(index, "date") else str(index)[:10]
        rows.append([
            target.instrument_id,
            target.name,
            target.type,
            target.code,
            target.exchange,
            target.currency,
            target.ticker,
            date_value,
            close_float,
            "yfinance",
        ])
    if not rows:
        return 0
    with csv_path.open("a", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerows(rows)
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export all domestic stock/ETF historical closes to CSV")
    parser.add_argument("--output", default=str(ROOT / "exports" / "domestic_stock_etf_history.csv"))
    parser.add_argument("--done", default=str(ROOT / "exports" / "domestic_stock_etf_history.done.jsonl"))
    parser.add_argument("--sleep", type=float, default=0.15)
    parser.add_argument("--limit", type=int, default=0, help="for smoke test; 0 means no limit")
    parser.add_argument("--include-gold", action="store_true", help="include instruments typed as gold")
    args = parser.parse_args()

    csv_path = Path(args.output)
    done_path = Path(args.done)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    done_path.parent.mkdir(parents=True, exist_ok=True)
    ensure_csv_header(csv_path)

    targets = load_targets(include_gold=args.include_gold)
    done = read_done_tickers(done_path)
    pending = [target for target in targets if target.ticker not in done]
    if args.limit > 0:
        pending = pending[: args.limit]

    print(
        json.dumps(
            {
                "output": str(csv_path),
                "done": str(done_path),
                "total_targets": len(targets),
                "already_done": len(done),
                "pending_this_run": len(pending),
            },
            ensure_ascii=False,
        ),
        flush=True,
    )

    total_rows = 0
    success = 0
    failed = 0
    empty = 0
    for idx, target in enumerate(pending, start=1):
        try:
            rows = export_one(target, csv_path)
            if rows:
                success += 1
                total_rows += rows
                status = "success"
            else:
                empty += 1
                status = "empty"
            append_done(done_path, target, rows, status)
            print(f"[{idx}/{len(pending)}] {target.ticker} {target.name} {status} rows={rows}", flush=True)
        except Exception as exc:
            failed += 1
            append_done(done_path, target, 0, "failed", str(exc))
            print(f"[{idx}/{len(pending)}] {target.ticker} {target.name} failed error={exc}", flush=True)
        time.sleep(args.sleep)

    print(
        json.dumps(
            {
                "completed_this_run": len(pending),
                "success": success,
                "empty": empty,
                "failed": failed,
                "rows_written_this_run": total_rows,
                "output": str(csv_path),
                "done": str(done_path),
            },
            ensure_ascii=False,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
