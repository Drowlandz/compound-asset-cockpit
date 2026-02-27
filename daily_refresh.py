#!/usr/bin/env python3
"""
Offline daily refresh for Compound Asset Cockpit.

What it does:
1) Refreshes macro cache (VIX/TNX/HSI vol/CNH) when network is available.
2) Refreshes prices for open STOCK positions and writes to stock_prices.
3) Computes latest net asset and writes one snapshot into daily_snapshots.

This script is designed to run from cron/launchd without opening Streamlit.
"""

from __future__ import annotations

import argparse
import logging
import warnings
from datetime import date, datetime
from typing import Dict, Optional, Tuple

# Silence common local SSL warning noise in scheduled logs.
warnings.filterwarnings(
    "ignore",
    message="urllib3 v2 only supports OpenSSL 1.1.1+",
)

import yfinance as yf

import data_manager as db
from services.market_data_service import detect_currency as shared_detect_currency
from services.market_data_service import fetch_realtime_price as shared_fetch_realtime_price
from services.market_data_service import get_exchange_rates as shared_get_exchange_rates
from services import transaction_service as tx_service

# Keep scheduled logs clean when network is temporarily unavailable.
logging.getLogger("yfinance").setLevel(logging.CRITICAL)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compound Asset Cockpit daily offline refresh")
    parser.add_argument(
        "--date",
        dest="snapshot_date",
        default=date.today().strftime("%Y-%m-%d"),
        help="Snapshot date in YYYY-MM-DD format (default: today)",
    )
    parser.add_argument(
        "--no-macro",
        action="store_true",
        help="Skip macro cache refresh",
    )
    parser.add_argument(
        "--no-price",
        action="store_true",
        help="Skip stock price refresh",
    )
    parser.add_argument(
        "--no-dca",
        action="store_true",
        help="Skip auto DCA execution",
    )
    parser.add_argument(
        "--force-snapshot",
        action="store_true",
        help="Write snapshot even if same values already exist for the date",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Only print the final summary line",
    )
    parser.add_argument(
        "--allow-historical-snapshot",
        action="store_true",
        help="Allow writing snapshot for a non-today date (not recommended)",
    )
    return parser.parse_args()


def detect_currency(symbol: str) -> str:
    return shared_detect_currency(symbol)


def get_exchange_rates() -> Dict[str, float]:
    return shared_get_exchange_rates()


def fetch_realtime_price(symbol: str, timeout_sec: float = 2.0) -> Optional[float]:
    return shared_fetch_realtime_price(symbol, timeout_sec=timeout_sec)


def refresh_macro_cache() -> Dict[str, float]:
    updated: Dict[str, float] = {}

    def fetch_and_store(ticker: str, key: str, period: str = "1d") -> None:
        try:
            hist = yf.Ticker(ticker).history(period=period)
            if hist.empty:
                return
            val = float(hist["Close"].iloc[-1])
            db.update_macro_cache(key, val)
            updated[key] = val
        except Exception:
            return

    fetch_and_store("^VIX", "vix")
    fetch_and_store("^TNX", "tnx")
    fetch_and_store("CNH=X", "cnh", period="5d")

    try:
        hist = yf.Ticker("^HSI").history(period="90d")
        if not hist.empty and "Close" in hist.columns:
            returns = hist["Close"].pct_change().dropna()
            if len(returns) >= 30:
                hsi_vol = float(returns.tail(30).std() * (252 ** 0.5) * 100)
                db.update_macro_cache("hsbfix", hsi_vol)
                updated["hsbfix"] = hsi_vol
    except Exception:
        pass

    return updated


def safe_float(val, default: float = 0.0) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def refresh_stock_prices(portfolio_df) -> Tuple[int, Dict[str, float]]:
    if portfolio_df.empty:
        return 0, {}

    updated: Dict[str, float] = {}
    seen = set()
    for _, row in portfolio_df.iterrows():
        if str(row.get("Type", "")).upper() != "STOCK":
            continue
        symbol = str(row.get("Raw Symbol", row.get("Symbol", ""))).strip().upper()
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        price = fetch_realtime_price(symbol)
        if price is None:
            continue
        db.upsert_stock_price(symbol, price, source="auto", asset_category="STOCK")
        updated[symbol] = price
    return len(updated), updated


def load_price_map() -> Dict[str, float]:
    return db.get_stock_price_map()


def load_snapshot_for_day(snapshot_date: str) -> Optional[Tuple[float, float]]:
    row = db.get_snapshot_by_date(snapshot_date)
    if not row:
        return None
    return safe_float(row[0]), safe_float(row[1])


def compute_net_asset(portfolio_df, price_map: Dict[str, float]) -> Tuple[float, float, float, float]:
    rates = get_exchange_rates()
    market_val_usd = 0.0

    if not portfolio_df.empty:
        for _, row in portfolio_df.iterrows():
            raw_sym = str(row.get("Raw Symbol", row.get("Symbol", ""))).strip().upper()
            qty = safe_float(row.get("Quantity"))
            mult = safe_float(row.get("Multiplier"), default=1.0)
            avg_cost = safe_float(row.get("Avg Cost"))
            row_type = str(row.get("Type", "STOCK")).upper()

            db_price = price_map.get(raw_sym)
            if row_type == "OPTION":
                price_native = db_price if db_price is not None else avg_cost
            else:
                price_native = db_price if db_price is not None else avg_cost

            currency = detect_currency(raw_sym)
            rate = rates.get(currency, 1.0)
            market_val_usd += price_native * qty * mult * rate

    cash_balance = safe_float(db.get_cash_balance())
    total_invested = safe_float(db.get_total_invested())
    net_asset = market_val_usd + cash_balance
    return net_asset, total_invested, market_val_usd, cash_balance


def should_write_snapshot(
    existing: Optional[Tuple[float, float]],
    total_asset: float,
    total_invested: float,
    force_snapshot: bool,
) -> bool:
    if force_snapshot or existing is None:
        return True
    old_asset, old_invested = existing
    return abs(old_asset - total_asset) >= 0.01 or abs(old_invested - total_invested) >= 0.01


def log(message: str, quiet: bool) -> None:
    if not quiet:
        print(message)


def main() -> int:
    args = parse_args()
    today_date = date.today().strftime("%Y-%m-%d")
    if args.snapshot_date != today_date and not args.allow_historical_snapshot:
        print(
            f"Refused to write historical snapshot: requested={args.snapshot_date}, today={today_date}. "
            "Use --allow-historical-snapshot only if you really need manual correction."
        )
        return 2

    today = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.init_db()

    log(f"[{today}] Daily refresh started", args.quiet)

    macro_count = 0
    if not args.no_macro:
        macro_updated = refresh_macro_cache()
        macro_count = len(macro_updated)
        log(f"Macro updated: {macro_count}", args.quiet)

    portfolio_df = db.get_portfolio_summary()
    if not portfolio_df.empty:
        portfolio_df["Quantity"] = portfolio_df["Quantity"].apply(safe_float)
        portfolio_df = portfolio_df[portfolio_df["Quantity"] >= 0.01]

    price_count = 0
    if not args.no_price:
        price_count, _ = refresh_stock_prices(portfolio_df)
        log(f"Stock prices updated: {price_count}", args.quiet)

    dca_summary = {"executed": 0, "skipped": 0, "failed": 0}
    if not args.no_dca and args.snapshot_date == today_date:
        dca_summary = tx_service.execute_due_dca_plans(datetime.now())
        log(
            f"DCA executed={dca_summary['executed']} skipped={dca_summary['skipped']} failed={dca_summary['failed']}",
            args.quiet,
        )
        # 自动定投可能改变持仓与现金，重新获取用于快照计算。
        portfolio_df = db.get_portfolio_summary()
        if not portfolio_df.empty:
            portfolio_df["Quantity"] = portfolio_df["Quantity"].apply(safe_float)
            portfolio_df = portfolio_df[portfolio_df["Quantity"] >= 0.01]
    elif not args.no_dca:
        log("Skip DCA execution for non-today snapshot date", args.quiet)

    price_map = load_price_map()
    net_asset, total_invested, market_val, cash = compute_net_asset(portfolio_df, price_map)
    existing_snapshot = load_snapshot_for_day(args.snapshot_date)

    wrote_snapshot = False
    if should_write_snapshot(existing_snapshot, net_asset, total_invested, args.force_snapshot):
        db.save_daily_snapshot(args.snapshot_date, net_asset, total_invested)
        wrote_snapshot = True

    summary = (
        f"date={args.snapshot_date} "
        f"net_asset={net_asset:.2f} "
        f"market_value={market_val:.2f} "
        f"cash={cash:.2f} "
        f"invested={total_invested:.2f} "
        f"macro_updated={macro_count} "
        f"prices_updated={price_count} "
        f"dca_executed={dca_summary['executed']} "
        f"dca_failed={dca_summary['failed']} "
        f"snapshot_written={int(wrote_snapshot)}"
    )
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
