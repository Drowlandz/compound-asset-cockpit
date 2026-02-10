from __future__ import annotations

from typing import Dict, Optional

import requests


def get_exchange_rates() -> Dict[str, float]:
    """Return base FX rates against USD."""
    return {"USD": 1.0, "HKD": 0.128, "CNY": 0.138, "CNH": 0.138}


def detect_currency(symbol: str) -> str:
    """Map instrument symbol to currency."""
    sym = str(symbol).lower().strip()
    if sym.isdigit() and len(sym) == 5:
        return "HKD"
    if sym.startswith("hk"):
        return "HKD"
    if sym.startswith("sh") or sym.startswith("sz") or (sym.isdigit() and len(sym) == 6):
        return "CNY"
    return "USD"


def fetch_realtime_price(symbol: str, timeout_sec: float = 2.0) -> Optional[float]:
    """
    Fetch realtime stock price from Sina endpoint.
    Returns None on parse/network failures.
    """
    sym = str(symbol).lower().strip()
    headers = {"Referer": "https://finance.sina.com.cn"}
    try:
        if " " in sym:
            return None

        if sym.isalpha():
            url = f"https://hq.sinajs.cn/list=gb_{sym}"
            resp = requests.get(url, headers=headers, timeout=timeout_sec)
            content = resp.text.split('="')[1].split(",")
            if len(content) > 1:
                return float(content[1])
        else:
            if not (sym.startswith("sh") or sym.startswith("sz") or sym.startswith("hk")):
                if len(sym) == 5:
                    prefix = "hk"
                else:
                    prefix = "sh" if sym.startswith("6") else "sz"
                sym = prefix + sym

            url = f"https://hq.sinajs.cn/list={sym}"
            resp = requests.get(url, headers=headers, timeout=timeout_sec)
            content = resp.text.split('="')[1].split(",")
            if len(content) > 3:
                return float(content[6] if "hk" in sym else content[3])
    except Exception:
        return None
    return None

