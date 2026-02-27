from __future__ import annotations

from typing import Callable, Dict, Tuple

import pandas as pd
from services.risk_rules import concentration_band
from services.risk_rules import leverage_band


def filter_active_positions(portfolio_df: pd.DataFrame, min_quantity: float = 0.01) -> pd.DataFrame:
    if portfolio_df is None or portfolio_df.empty:
        return pd.DataFrame()

    df = portfolio_df.copy()
    df["Quantity"] = pd.to_numeric(df.get("Quantity"), errors="coerce").fillna(0.0)
    return df[df["Quantity"] >= min_quantity].copy()


def get_highest_badge(
    portfolio_df: pd.DataFrame,
    badge_resolver: Callable[[float], Tuple[str, str]],
) -> Tuple[float, str, str]:
    max_days_held = 0.0
    badge_icon = "🌱"
    badge_name = "新手"

    if portfolio_df is None or portfolio_df.empty:
        return max_days_held, badge_icon, badge_name

    if "Days Held" not in portfolio_df.columns or portfolio_df["Days Held"].isnull().all():
        return max_days_held, badge_icon, badge_name

    max_days_held = float(portfolio_df["Days Held"].max())
    badge_icon, badge_name = badge_resolver(max_days_held)
    return max_days_held, badge_icon, badge_name


def calculate_account_metrics(
    portfolio_df: pd.DataFrame,
    cash_balance: float,
    total_invested: float,
) -> Dict[str, float]:
    market_val_usd = 0.0
    total_cost_usd = 0.0
    top3_conc = 0.0

    if portfolio_df is not None and not portfolio_df.empty:
        market_val_usd = float(pd.to_numeric(portfolio_df.get("Market Value"), errors="coerce").fillna(0.0).sum())
        total_cost_usd = float(pd.to_numeric(portfolio_df.get("Total Cost"), errors="coerce").fillna(0.0).sum())
        if market_val_usd > 0:
            top3_val = float(
                pd.to_numeric(portfolio_df.nlargest(3, "Market Value").get("Market Value"), errors="coerce")
                .fillna(0.0)
                .sum()
            )
            top3_conc = top3_val / market_val_usd * 100

    final_net_asset = market_val_usd + float(cash_balance)
    base = float(total_invested)
    pnl = final_net_asset - base
    ret_pct = (pnl / base * 100) if base > 0 else 0.0
    holding_ratio_pct = (market_val_usd / final_net_asset * 100) if abs(final_net_asset) > 1e-9 else 0.0
    lev_ratio = (market_val_usd / final_net_asset) if final_net_asset > 0 else 999.0
    cash_ratio = (float(cash_balance) / final_net_asset * 100) if final_net_asset > 0 else 0.0

    return {
        "market_val_usd": market_val_usd,
        "total_cost_usd": total_cost_usd,
        "final_net_asset": final_net_asset,
        "base": base,
        "pnl": pnl,
        "ret_pct": ret_pct,
        "holding_ratio_pct": holding_ratio_pct,
        "lev_ratio": lev_ratio,
        "cash_ratio": cash_ratio,
        "top3_conc": top3_conc,
    }


def concentration_status(top3_conc: float) -> Tuple[str, str]:
    band = concentration_band(top3_conc)
    if band == "critical_low":
        return "过低", "inverse"
    if band == "warning_low":
        return "偏低", "inverse"
    if band == "info_low":
        return "接近阈值", "off"
    return "良好 ✓", "normal"


def leverage_status(lev_ratio: float) -> Tuple[str, str]:
    if leverage_band(lev_ratio) in ("info_high", "warning_high", "critical_high"):
        return "偏高", "inverse"
    return "安全", "normal"


def _calc_safety_margin(row: pd.Series) -> float:
    asset_type = str(row.get("Type", "")).upper()
    if asset_type not in ("STOCK", "OPTION"):
        return 0.0
    try:
        price = float(row.get("Price", 0) or 0)
        avg_cost = float(row.get("Avg Cost", 0) or 0)
    except (TypeError, ValueError):
        return 0.0
    if price <= 0:
        return 0.0
    return (price - avg_cost) / price * 100


def build_holdings_display_df(
    portfolio_df: pd.DataFrame,
    badge_resolver: Callable[[float], Tuple[str, str]],
) -> pd.DataFrame:
    if portfolio_df is None or portfolio_df.empty:
        return pd.DataFrame()

    df = portfolio_df.copy()
    if "Market Value" not in df.columns:
        df["Market Value"] = 0.0
    if "Total Cost" not in df.columns:
        df["Total Cost"] = 0.0
    if "Days Held" not in df.columns:
        df["Days Held"] = 0.0

    df["PnL $"] = pd.to_numeric(df["Market Value"], errors="coerce").fillna(0.0) - pd.to_numeric(
        df["Total Cost"], errors="coerce"
    ).fillna(0.0)
    df["Safety Margin"] = df.apply(_calc_safety_margin, axis=1)
    df["Badge"] = df["Days Held"].apply(lambda d: " ".join(badge_resolver(d)))
    # Keep top-impact positions first and maintain stable ordering for ties.
    df["Market Value"] = pd.to_numeric(df["Market Value"], errors="coerce").fillna(0.0)
    df["_symbol_sort"] = df.get("Symbol", pd.Series(dtype=str)).astype(str)
    df = df.sort_values(["Market Value", "_symbol_sort"], ascending=[False, True], kind="mergesort")
    return df.drop(columns=["_symbol_sort"])
