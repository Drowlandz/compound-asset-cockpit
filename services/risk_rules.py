from __future__ import annotations

# Portfolio concentration thresholds (%)
TOP3_CONC_CRITICAL = 60.0
TOP3_CONC_WARNING = 70.0
TOP3_CONC_INFO = 80.0

# Leverage thresholds (x)
LEVERAGE_INFO = 1.2
LEVERAGE_WARNING = 1.5
LEVERAGE_CRITICAL = 2.0

# Sector concentration thresholds (%)
SECTOR_CONC_INFO = 60.0
SECTOR_CONC_WARNING = 70.0
SECTOR_CONC_CRITICAL = 80.0


def concentration_band(top3_conc: float) -> str:
    if top3_conc < TOP3_CONC_CRITICAL:
        return "critical_low"
    if top3_conc < TOP3_CONC_WARNING:
        return "warning_low"
    if top3_conc < TOP3_CONC_INFO:
        return "info_low"
    return "normal"


def leverage_band(leverage: float) -> str:
    if leverage > LEVERAGE_CRITICAL:
        return "critical_high"
    if leverage > LEVERAGE_WARNING:
        return "warning_high"
    if leverage > LEVERAGE_INFO:
        return "info_high"
    return "normal"


def sector_concentration_band(pct: float) -> str:
    if pct > SECTOR_CONC_CRITICAL:
        return "critical_high"
    if pct > SECTOR_CONC_WARNING:
        return "warning_high"
    if pct > SECTOR_CONC_INFO:
        return "info_high"
    return "normal"

