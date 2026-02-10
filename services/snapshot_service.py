from __future__ import annotations

from datetime import date

import data_manager as db


def save_today_snapshot(total_asset: float, total_invested: float) -> None:
    snapshot_date = date.today().strftime("%Y-%m-%d")
    db.save_daily_snapshot(snapshot_date, total_asset, total_invested)

