import unittest

import pandas as pd

from services import portfolio_service as pf_service
from services import transaction_service as tx_service
from services.risk_rules import concentration_band
from services.risk_rules import leverage_band
from services.risk_rules import sector_concentration_band


class TestRiskRules(unittest.TestCase):
    def test_concentration_band_boundaries(self):
        self.assertEqual(concentration_band(59.9), "critical_low")
        self.assertEqual(concentration_band(60.0), "warning_low")
        self.assertEqual(concentration_band(70.0), "info_low")
        self.assertEqual(concentration_band(80.0), "normal")

    def test_leverage_band_boundaries(self):
        self.assertEqual(leverage_band(1.2), "normal")
        self.assertEqual(leverage_band(1.21), "info_high")
        self.assertEqual(leverage_band(1.51), "warning_high")
        self.assertEqual(leverage_band(2.01), "critical_high")

    def test_sector_band_boundaries(self):
        self.assertEqual(sector_concentration_band(60.0), "normal")
        self.assertEqual(sector_concentration_band(60.1), "info_high")
        self.assertEqual(sector_concentration_band(70.1), "warning_high")
        self.assertEqual(sector_concentration_band(80.1), "critical_high")


class TestPortfolioService(unittest.TestCase):
    def test_filter_active_positions(self):
        df = pd.DataFrame(
            [
                {"Symbol": "A", "Quantity": 0.0},
                {"Symbol": "B", "Quantity": 0.02},
            ]
        )
        result = pf_service.filter_active_positions(df)
        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0]["Symbol"], "B")

    def test_calculate_account_metrics(self):
        portfolio_df = pd.DataFrame(
            [
                {"Market Value": 300.0, "Total Cost": 250.0},
                {"Market Value": 100.0, "Total Cost": 120.0},
                {"Market Value": 50.0, "Total Cost": 30.0},
            ]
        )
        metrics = pf_service.calculate_account_metrics(
            portfolio_df=portfolio_df,
            cash_balance=50.0,
            total_invested=300.0,
        )

        self.assertAlmostEqual(metrics["market_val_usd"], 450.0)
        self.assertAlmostEqual(metrics["final_net_asset"], 500.0)
        self.assertAlmostEqual(metrics["pnl"], 200.0)
        self.assertAlmostEqual(metrics["ret_pct"], 66.66666666666666)
        self.assertAlmostEqual(metrics["top3_conc"], 100.0)


class TestTransactionService(unittest.TestCase):
    def test_parse_float_input_ok(self):
        value, err = tx_service.parse_float_input("1,234.50", "金额", min_value=0.0)
        self.assertIsNone(err)
        self.assertAlmostEqual(value, 1234.5)

    def test_parse_float_input_empty(self):
        value, err = tx_service.parse_float_input("", "金额", min_value=0.0)
        self.assertIsNone(value)
        self.assertIn("不能为空", err)

    def test_parse_float_input_invalid(self):
        value, err = tx_service.parse_float_input("abc", "金额", min_value=0.0)
        self.assertIsNone(value)
        self.assertIn("有效数字", err)

    def test_parse_float_input_below_min(self):
        value, err = tx_service.parse_float_input("-1", "金额", min_value=0.0)
        self.assertIsNone(value)
        self.assertIn("不能小于", err)


if __name__ == "__main__":
    unittest.main()
