import os
import shutil
import sqlite3
import tempfile
import unittest

import data_manager as db


class TestDataManagerRegression(unittest.TestCase):
    def setUp(self):
        self.original_db_name = db.DB_NAME
        self.temp_dir = tempfile.mkdtemp(prefix="im_test_db_")
        self.test_db = os.path.join(self.temp_dir, "investments.db")
        db.DB_NAME = self.test_db
        db.init_db()

    def tearDown(self):
        db.DB_NAME = self.original_db_name
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _insert_raw_transaction(
        self,
        *,
        date,
        symbol,
        tx_type,
        quantity,
        price,
        fee,
        asset_category,
        multiplier=1,
        note="",
        is_deleted=0,
    ) -> int:
        conn = sqlite3.connect(db.DB_NAME)
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO transactions
            (date, symbol, type, quantity, price, fee, note, asset_category, multiplier, is_deleted)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (date, symbol, tx_type, quantity, price, fee, note, asset_category, multiplier, is_deleted),
        )
        tx_id = c.lastrowid
        conn.commit()
        conn.close()
        return int(tx_id)

    def test_soft_delete_restore_handles_legacy_lowercase_buy(self):
        tx_id = self._insert_raw_transaction(
            date="2026-02-01",
            symbol="pltr",
            tx_type="buy",
            quantity=1.0,
            price=100.0,
            fee=1.0,
            asset_category="stock",
            note="legacy row",
        )

        portfolio_before = db.get_portfolio_summary()
        qty_before = float(portfolio_before.loc[portfolio_before["Raw Symbol"] == "PLTR", "Quantity"].sum())
        self.assertAlmostEqual(qty_before, 1.0)

        db.soft_delete_transaction(tx_id)
        self.assertAlmostEqual(db.get_cash_balance(), 101.0)

        portfolio_deleted = db.get_portfolio_summary()
        self.assertTrue(portfolio_deleted.empty)

        db.restore_transaction(tx_id)
        self.assertAlmostEqual(db.get_cash_balance(), 0.0)

        portfolio_restored = db.get_portfolio_summary()
        qty_restored = float(portfolio_restored.loc[portfolio_restored["Raw Symbol"] == "PLTR", "Quantity"].sum())
        self.assertAlmostEqual(qty_restored, 1.0)

    def test_portfolio_summary_separates_stock_and_option_same_symbol(self):
        db.add_transaction(
            date="2026-02-10",
            symbol="TSLA",
            type="BUY",
            quantity=1,
            price=10,
            fee=1,
            note="open option",
            asset_category="OPTION",
            multiplier=100,
            strike=300,
            expiration="2026-03-20",
            option_type="CALL",
        )
        db.add_transaction(
            date="2026-02-11",
            symbol="TSLA",
            type="BUY",
            quantity=2,
            price=300,
            fee=1,
            note="buy stock",
            asset_category="STOCK",
            multiplier=1,
        )

        portfolio = db.get_portfolio_summary()
        same_underlying = portfolio[portfolio["Raw Symbol"] == "TSLA"].copy()

        self.assertEqual(set(same_underlying["Type"].tolist()), {"STOCK", "OPTION"})
        self.assertEqual(len(same_underlying), 2)

        stock_row = same_underlying[same_underlying["Type"] == "STOCK"].iloc[0]
        option_row = same_underlying[same_underlying["Type"] == "OPTION"].iloc[0]

        self.assertAlmostEqual(float(stock_row["Quantity"]), 2.0)
        self.assertAlmostEqual(float(option_row["Quantity"]), 1.0)
        self.assertEqual(str(stock_row["Symbol"]), "TSLA")
        self.assertIn("TSLA", str(option_row["Symbol"]))

    def test_stock_holdings_sell_uses_case_insensitive_direction(self):
        self._insert_raw_transaction(
            date="2026-02-01",
            symbol="nvda",
            tx_type="buy",
            quantity=3.0,
            price=100.0,
            fee=0.0,
            asset_category="stock",
        )
        self._insert_raw_transaction(
            date="2026-02-02",
            symbol="NVDA",
            tx_type="SELL",
            quantity=1.0,
            price=120.0,
            fee=0.0,
            asset_category="STOCK",
        )

        holdings = db.get_stock_holdings_for_sell()
        self.assertEqual(len(holdings), 1)
        self.assertEqual(str(holdings.iloc[0]["Symbol"]), "NVDA")
        self.assertAlmostEqual(float(holdings.iloc[0]["Quantity"]), 2.0)


if __name__ == "__main__":
    unittest.main()
