import sqlite3
import pandas as pd
import os
import sys
from datetime import date, datetime

# === 路径修正逻辑 ===
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_NAME = os.path.join(BASE_DIR, "investments.db")


def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # 交易表
    c.execute('''CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        symbol TEXT NOT NULL,
        type TEXT NOT NULL,
        quantity REAL NOT NULL,
        price REAL NOT NULL,
        fee REAL DEFAULT 0,
        note TEXT,
        asset_category TEXT DEFAULT 'STOCK',
        multiplier INTEGER DEFAULT 1,
        strike REAL,
        expiration TEXT,
        option_type TEXT,
        is_deleted INTEGER DEFAULT 0
    )''')

    # 资金/本金流水表
    c.execute('''CREATE TABLE IF NOT EXISTS fund_flows (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        type TEXT NOT NULL, -- DEPOSIT, WITHDRAW, RESET
        amount REAL NOT NULL,
        note TEXT
    )''')

    # 每日快照
    c.execute('''CREATE TABLE IF NOT EXISTS daily_snapshots (
        date TEXT PRIMARY KEY,
        total_asset REAL,
        total_invested REAL
    )''')

    # 现金余额
    c.execute('''CREATE TABLE IF NOT EXISTS cash_balance (
        id INTEGER PRIMARY KEY,
        balance REAL DEFAULT 0
    )''')
    c.execute("INSERT OR IGNORE INTO cash_balance (id, balance) VALUES (1, 0)")

    # 自动修复
    try:
        c.execute("SELECT total_invested FROM daily_snapshots LIMIT 1")
    except sqlite3.OperationalError:
        c.execute("ALTER TABLE daily_snapshots ADD COLUMN total_invested REAL DEFAULT 0")

    conn.commit()
    conn.close()


# ================= 交易部分 (不变) =================

def add_transaction(date, symbol, type, quantity, price, fee, note, asset_category='STOCK', multiplier=1, strike=None,
                    expiration=None, option_type=None):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''INSERT INTO transactions 
        (date, symbol, type, quantity, price, fee, note, asset_category, multiplier, strike, expiration, option_type)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (date, symbol, type, quantity, price, fee, note, asset_category, multiplier, strike, expiration,
               option_type))

    total_amt = quantity * price * multiplier
    if type == 'BUY':
        change = -(total_amt + fee)
    else:
        change = (total_amt - fee)

    c.execute("UPDATE cash_balance SET balance = balance + ? WHERE id = 1", (change,))
    conn.commit()
    conn.close()


def soft_delete_transaction(trans_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT type, quantity, price, fee, multiplier, is_deleted FROM transactions WHERE id = ?", (trans_id,))
    row = c.fetchone()
    if row and row[5] == 0:
        t_type, qty, price, fee, mult, _ = row
        total_amt = qty * price * mult
        if t_type == 'BUY':
            rollback = total_amt + fee
        else:
            rollback = -(total_amt - fee)
        c.execute("UPDATE cash_balance SET balance = balance + ? WHERE id = 1", (rollback,))
        c.execute("UPDATE transactions SET is_deleted = 1 WHERE id = ?", (trans_id,))
    conn.commit()
    conn.close()


def restore_transaction(trans_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT type, quantity, price, fee, multiplier FROM transactions WHERE id = ?", (trans_id,))
    row = c.fetchone()
    if row:
        t_type, qty, price, fee, mult = row
        total_amt = qty * price * mult
        if t_type == 'BUY':
            change = -(total_amt + fee)
        else:
            change = (total_amt - fee)
        c.execute("UPDATE cash_balance SET balance = balance + ? WHERE id = 1", (change,))
        c.execute("UPDATE transactions SET is_deleted = 0 WHERE id = ?", (trans_id,))
    conn.commit()
    conn.close()


def get_all_transactions(include_deleted=False):
    conn = sqlite3.connect(DB_NAME)
    query = "SELECT * FROM transactions"
    if not include_deleted: query += " WHERE is_deleted = 0"
    query += " ORDER BY date DESC, id DESC"
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df


def get_deleted_transactions_last_7_days():
    conn = sqlite3.connect(DB_NAME)
    query = "SELECT * FROM transactions WHERE is_deleted = 1 ORDER BY id DESC LIMIT 50"
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df


def get_portfolio_summary():
    df = get_all_transactions(include_deleted=False)
    if df.empty: return pd.DataFrame()

    portfolio = {}
    df_sorted = df.sort_values(by=['symbol', 'date', 'id'], ascending=[True, True, True])

    for _, row in df_sorted.iterrows():
        sym = row['symbol']
        if sym not in portfolio:
            portfolio[sym] = {
                'Symbol': sym, 'Raw Symbol': sym if row['asset_category'] == 'STOCK' else (
                    row['symbol'].split()[0] if ' ' in row['symbol'] else row['symbol']),
                'Quantity': 0.0, 'Total Cost': 0.0, 'Multiplier': row['multiplier'], 'Type': row['asset_category'],
                'Days Held': 0, 'First Buy Date': None
            }
        p = portfolio[sym]
        qty = float(row['quantity'])
        price = float(row['price'])
        fee = float(row['fee'])
        mult = int(row['multiplier'])

        if row['type'] == 'BUY':
            p['Total Cost'] += (qty * price * mult) + fee
            p['Quantity'] += qty
            if p['First Buy Date'] is None: p['First Buy Date'] = datetime.strptime(row['date'], '%Y-%m-%d').date()
        elif row['type'] == 'SELL':
            if p['Quantity'] > 0:
                avg_cost = p['Total Cost'] / p['Quantity']
                p['Total Cost'] -= avg_cost * qty
                p['Quantity'] -= qty
            else:
                p['Quantity'] -= qty

    result = []
    today = date.today()
    for sym, data in portfolio.items():
        if data['Quantity'] > 0.001:
            data['Avg Cost'] = (data['Total Cost'] / data['Quantity'] / data['Multiplier']) if data[
                                                                                                   'Quantity'] > 0 else 0
            if data['First Buy Date']: data['Days Held'] = (today - data['First Buy Date']).days
            del data['First Buy Date']
            result.append(data)

    return pd.DataFrame(result) if result else pd.DataFrame()


# ================= 🔥 核心：本金与现金管理 (已修正) =================

def manage_principal(date, p_type, amount, note):
    """
    入金/出金：同时影响本金和现金
    """
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # 1. 记录流水
    c.execute("INSERT INTO fund_flows (date, type, amount, note) VALUES (?, ?, ?, ?)", (date, p_type, amount, note))

    # 2. 变更现金 (入金加钱，出金减钱)
    change = amount if p_type == 'DEPOSIT' else -amount
    c.execute("UPDATE cash_balance SET balance = balance + ? WHERE id = 1", (change,))

    conn.commit()
    conn.close()


def reset_principal_only(amount, date_str):
    """
    🔥 重置本金：只改变【本金统计】，不改变【现金余额】
    用于重新设定利润计算的基准点。
    """
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # 1. 清空旧流水
    c.execute("DELETE FROM fund_flows")

    # 2. 插入一条 RESET 记录作为新起点
    c.execute("INSERT INTO fund_flows (date, type, amount, note) VALUES (?, 'RESET', ?, '本金基准重置')",
              (date_str, amount))

    # 🔥 注意：这里没有 UPDATE cash_balance 的操作！

    conn.commit()
    conn.close()


def delete_fund_flow(f_id):
    """删除流水"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT type, amount FROM fund_flows WHERE id=?", (f_id,))
    row = c.fetchone()
    if row:
        f_type, amt = row

        # 🔥 如果是入金/出金，需要回滚现金
        if f_type in ['DEPOSIT', 'WITHDRAW']:
            rollback = -amt if f_type == 'DEPOSIT' else amt
            c.execute("UPDATE cash_balance SET balance = balance + ? WHERE id = 1", (rollback,))

        # 如果是 RESET，不需要回滚现金，直接删记录即可

        c.execute("DELETE FROM fund_flows WHERE id=?", (f_id,))
    conn.commit()
    conn.close()


def get_total_invested():
    """计算总本金"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        # DEPOSIT / RESET 算正，WITHDRAW 算负
        c.execute("""
            SELECT SUM(
                CASE 
                    WHEN type IN ('DEPOSIT', 'RESET') THEN amount 
                    WHEN type = 'WITHDRAW' THEN -amount 
                    ELSE 0 
                END
            ) FROM fund_flows
        """)
        res = c.fetchone()
        return res[0] if res and res[0] else 0.0
    except:
        return 0.0
    finally:
        conn.close()


def get_cash_balance():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT balance FROM cash_balance WHERE id=1")
    res = c.fetchone()
    conn.close()
    return res[0] if res else 0.0


def set_cash_balance(new_balance):
    """单纯校准现金（不产生流水，用于对账）"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE cash_balance SET balance = ? WHERE id = 1", (new_balance,))
    conn.commit()
    conn.close()


def get_fund_flows():
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM fund_flows ORDER BY date DESC", conn)
    conn.close()
    return df


# ================= 快照 =================
def save_daily_snapshot(date_str, asset, invested):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO daily_snapshots (date, total_asset, total_invested) VALUES (?, ?, ?)",
              (date_str, asset, invested))
    conn.commit()
    conn.close()


def get_history_data():
    conn = sqlite3.connect(DB_NAME)
    try:
        df = pd.read_sql_query("SELECT * FROM daily_snapshots ORDER BY date ASC", conn)
        if not df.empty and 'total_invested' in df.columns:
            df['total_pnl'] = df['total_asset'] - df['total_invested']
        return df
    except:
        return pd.DataFrame()
    finally:
        conn.close()