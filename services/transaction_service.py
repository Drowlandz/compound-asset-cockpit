from __future__ import annotations

from typing import Optional, Tuple

import data_manager as db


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


def add_stock_transaction(
    t_date,
    t_sym: str,
    final_type: str,
    t_qty: float,
    t_price: float,
    t_fee: float,
    t_note: str,
) -> None:
    db.add_transaction(
        t_date,
        t_sym,
        final_type,
        t_qty,
        t_price,
        t_fee,
        t_note,
        asset_category="STOCK",
        multiplier=1,
    )


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

