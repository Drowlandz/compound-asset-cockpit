from __future__ import annotations

import calendar
from decimal import Decimal
from decimal import ROUND_HALF_UP
from datetime import date as dt_date
from datetime import datetime
from datetime import timedelta
from typing import Dict, List, Optional, Tuple

import data_manager as db
from services.market_data_service import fetch_realtime_price

STOCK_QTY_SCALE = Decimal("0.01")


def parse_float_input(raw_text, field_label: str, min_value: Optional[float] = None) -> Tuple[Optional[float], Optional[str]]:
    text = str(raw_text).strip().replace(",", "")
    if text == "":
        return None, f"{field_label} 不能为空"
    try:
        value = float(text)
    except ValueError:
        return None, f"{field_label} 请输入有效数字"
    if min_value is not None and value < min_value:
        return None, f"{field_label} 不能小于 {min_value:g}"
    return value, None


def parse_int_input(raw_text, field_label: str, min_value: Optional[int] = None) -> Tuple[Optional[int], Optional[str]]:
    text = str(raw_text).strip().replace(",", "")
    if text == "":
        return None, f"{field_label} 不能为空"
    if any(ch in text for ch in [".", "e", "E"]):
        return None, f"{field_label} 请输入正整数"
    try:
        value = int(text)
    except ValueError:
        return None, f"{field_label} 请输入正整数"
    if min_value is not None and value < min_value:
        return None, f"{field_label} 不能小于 {min_value}"
    return value, None


def round_stock_quantity(raw_qty: float) -> float:
    return float(Decimal(str(raw_qty)).quantize(STOCK_QTY_SCALE, rounding=ROUND_HALF_UP))


def _add_months(base_date: dt_date, months: int) -> dt_date:
    month_index = (base_date.month - 1) + months
    year = base_date.year + (month_index // 12)
    month = (month_index % 12) + 1
    day = min(base_date.day, calendar.monthrange(year, month)[1])
    return dt_date(year, month, day)


def build_dca_dates(start_date: dt_date, cadence: str, periods: int) -> List[dt_date]:
    if periods <= 0:
        return []
    if cadence == "每天":
        return [start_date + timedelta(days=i) for i in range(periods)]
    if cadence == "每周":
        return [start_date + timedelta(days=7 * i) for i in range(periods)]
    if cadence == "每月":
        return [_add_months(start_date, i) for i in range(periods)]
    raise ValueError(f"不支持的定投周期: {cadence}")


def add_stock_transaction(
    t_date,
    t_sym: str,
    final_type: str,
    t_qty: float,
    t_price: float,
    t_fee: float,
    t_note: str,
) -> int:
    qty_rounded = round_stock_quantity(t_qty)
    if qty_rounded < 0.01:
        raise ValueError("股票数量最少为 0.01 股")
    tx_id = db.add_transaction(
        t_date,
        t_sym,
        final_type,
        qty_rounded,
        t_price,
        t_fee,
        t_note,
        asset_category="STOCK",
        multiplier=1,
    )
    if str(final_type).upper().strip() == "SELL":
        # 卖出可能是回填历史日期，直接重算可保证按日期顺序结算 lot。
        db.rebuild_dca_lot_states()
    return tx_id


def add_stock_dca_transactions(
    start_date: dt_date,
    symbol: str,
    amount_per_period: float,
    price: float,
    fee: float,
    note: str,
    cadence: str,
    periods: int,
) -> Tuple[int, float, float, dt_date, dt_date]:
    dca_dates = build_dca_dates(start_date, cadence, periods)
    if not dca_dates:
        raise ValueError("定投期数必须大于 0")
    if amount_per_period <= fee:
        raise ValueError("每期定投总金额必须大于佣金")
    qty_per_period = round_stock_quantity((amount_per_period - fee) / price)
    if qty_per_period < 0.01:
        raise ValueError("按当前金额与价格计算后每期不足 0.01 股，请提高金额")
    base_note = f"定投[{cadence}] 每期={amount_per_period:g}"
    for idx, d in enumerate(dca_dates, start=1):
        dca_note = f"{base_note} 第{idx}/{periods}期"
        final_note = dca_note if not str(note).strip() else f"{dca_note} | {note}"
        add_stock_transaction(d, symbol, "BUY", qty_per_period, price, fee, final_note)
    total_qty = round_stock_quantity(qty_per_period * len(dca_dates))
    return len(dca_dates), qty_per_period, total_qty, dca_dates[0], dca_dates[-1]


def add_option_transaction(
    o_date,
    o_sym: str,
    o_side: str,
    o_qty: float,
    o_price: float,
    o_fee: float,
    o_type: str,
    o_strike: float,
    o_exp,
) -> None:
    db.add_transaction(
        o_date,
        o_sym,
        o_side,
        o_qty,
        o_price,
        o_fee,
        f"Option {o_type} {o_strike}",
        asset_category="OPTION",
        multiplier=100,
        strike=o_strike,
        expiration=str(o_exp),
        option_type=o_type,
    )


def open_dca_plan(
    symbol: str,
    amount_per_day: float,
    fee: float,
    start_date: dt_date,
    note: str = "",
    run_hour: int = 23,
    run_minute: int = 0,
) -> Tuple[int, str]:
    symbol_text = str(symbol).upper().strip()
    if not symbol_text:
        raise ValueError("股票代码不能为空")
    amount = float(amount_per_day)
    fee_val = float(fee)
    if amount <= 0:
        raise ValueError("每日定投总金额必须大于 0")
    if fee_val < 0:
        raise ValueError("佣金不能小于 0")
    if amount <= fee_val:
        raise ValueError("每日定投总金额必须大于佣金")
    if run_hour < 0 or run_hour > 23 or run_minute < 0 or run_minute > 59:
        raise ValueError("执行时间无效")
    return db.upsert_dca_plan(
        symbol=symbol_text,
        amount=amount,
        fee=fee_val,
        start_date=start_date,
        note=str(note or "").strip(),
        run_hour=int(run_hour),
        run_minute=int(run_minute),
    )


def pause_dca_plan(plan_id: int) -> None:
    db.set_dca_plan_status(int(plan_id), "PAUSED")


def resume_dca_plan(plan_id: int) -> None:
    db.set_dca_plan_status(int(plan_id), "ACTIVE")


def is_dca_plan_due(plan: Dict, now_dt: datetime) -> bool:
    status = str(plan.get("status", "")).upper().strip()
    if status != "ACTIVE":
        return False

    run_date = now_dt.strftime("%Y-%m-%d")
    start_date = str(plan.get("start_date") or run_date)[:10]
    if start_date > run_date:
        return False

    last_run_date = str(plan.get("last_run_date") or "").strip()[:10]
    if last_run_date == run_date:
        return False

    run_hour = int(plan.get("run_hour") or 23)
    run_minute = int(plan.get("run_minute") or 0)
    now_m = now_dt.hour * 60 + now_dt.minute
    target_m = run_hour * 60 + run_minute
    return now_m >= target_m


def _execute_dca_plan_once(plan: Dict, run_dt: datetime, run_mode: str, allow_same_day: bool) -> Dict:
    plan_id = int(plan["id"])
    symbol = str(plan["symbol"]).upper().strip()
    run_date = run_dt.strftime("%Y-%m-%d")
    run_at = run_dt.strftime("%Y-%m-%d %H:%M:%S")
    amount = float(plan.get("amount") or 0.0)
    fee = float(plan.get("fee") or 0.0)

    if not allow_same_day and db.has_success_dca_run(plan_id, run_date):
        return {"status": "skipped", "message": "今日已执行"}
    if amount <= fee:
        msg = "定投金额必须大于佣金"
        db.insert_dca_run(plan_id, run_at, run_date, symbol, None, amount, fee, None, None, "FAILED", run_mode, msg)
        return {"status": "failed", "message": msg}

    price = fetch_realtime_price(symbol)
    if price is None:
        price = db.get_stock_price(symbol)
    if price is None or float(price) <= 0:
        msg = "未获取到有效股价"
        db.insert_dca_run(plan_id, run_at, run_date, symbol, None, amount, fee, None, None, "FAILED", run_mode, msg)
        return {"status": "failed", "message": msg}

    qty = round_stock_quantity((amount - fee) / float(price))
    if qty < 0.01:
        msg = "按当前股价计算后不足 0.01 股"
        db.insert_dca_run(plan_id, run_at, run_date, symbol, float(price), amount, fee, qty, None, "FAILED", run_mode, msg)
        return {"status": "failed", "message": msg}

    plan_note = str(plan.get("note") or "").strip()
    auto_note = f"自动定投[plan#{plan_id}]"
    final_note = auto_note if not plan_note else f"{auto_note} | {plan_note}"
    tx_id = db.add_transaction(
        run_date,
        symbol,
        "BUY",
        qty,
        float(price),
        fee,
        final_note,
        asset_category="STOCK",
        multiplier=1,
        strategy_type="DCA",
        strategy_id=plan_id,
    )
    db.upsert_stock_price(symbol, float(price), source="auto", asset_category="STOCK")
    db.insert_dca_run(
        plan_id,
        run_at,
        run_date,
        symbol,
        float(price),
        amount,
        fee,
        qty,
        tx_id,
        "SUCCESS",
        run_mode,
        "",
    )
    db.add_dca_lot(plan_id, tx_id, symbol, run_date, qty, float(price), fee)
    db.set_dca_plan_last_run(plan_id, run_date, run_at)
    return {"status": "success", "message": "ok", "tx_id": tx_id, "qty": qty, "price": float(price)}


def execute_due_dca_plans(now_dt: Optional[datetime] = None) -> Dict[str, int]:
    now_dt = now_dt or datetime.now()
    plans_df = db.get_dca_plans(include_paused=False)
    summary = {"executed": 0, "skipped": 0, "failed": 0}
    if plans_df.empty:
        return summary

    for _, row in plans_df.iterrows():
        plan = {
            "id": int(row["id"]),
            "symbol": str(row["symbol"]),
            "amount": float(row["amount"]),
            "fee": float(row.get("fee", 0.0) or 0.0),
            "run_hour": int(row.get("run_hour", 23) or 23),
            "run_minute": int(row.get("run_minute", 0) or 0),
            "start_date": str(row.get("start_date", "")),
            "status": str(row.get("status", "PAUSED")),
            "note": str(row.get("note", "") or ""),
            "last_run_date": str(row.get("last_run_date", "") or ""),
        }
        if not is_dca_plan_due(plan, now_dt):
            summary["skipped"] += 1
            continue
        result = _execute_dca_plan_once(plan, now_dt, run_mode="SCHEDULED", allow_same_day=False)
        if result["status"] == "success":
            summary["executed"] += 1
        elif result["status"] == "failed":
            summary["failed"] += 1
        else:
            summary["skipped"] += 1
    return summary


def run_dca_plan_now(plan_id: int, now_dt: Optional[datetime] = None) -> Dict:
    now_dt = now_dt or datetime.now()
    plan = db.get_dca_plan(int(plan_id))
    if plan is None:
        return {"status": "failed", "message": "计划不存在"}
    return _execute_dca_plan_once(plan, now_dt, run_mode="MANUAL", allow_same_day=True)


def save_option_price(selected: dict, option_price: float) -> str:
    option_symbol_key = db.build_option_price_symbol(
        selected["symbol"],
        selected["expiration"],
        selected["option_type"],
        selected.get("strike"),
    )
    db.upsert_stock_price(
        option_symbol_key,
        option_price,
        source="manual",
        asset_category="OPTION",
    )
    return option_symbol_key


def apply_fund_flow(f_date, mode: str, amount: float, note: str) -> None:
    type_code = "DEPOSIT" if mode == "➕ 入金" else "WITHDRAW"
    db.manage_principal(f_date, type_code, amount, note)


def reset_principal(f_date, amount: float) -> None:
    db.reset_principal_only(amount, f_date)


def calibrate_cash(amount: float) -> None:
    db.set_cash_balance(amount)


def delete_fund_flow(record_id: int) -> None:
    db.delete_fund_flow(record_id)


def restore_transaction(trans_id: int) -> None:
    db.restore_transaction(trans_id)


def soft_delete_transaction(trans_id: int) -> None:
    db.soft_delete_transaction(trans_id)
