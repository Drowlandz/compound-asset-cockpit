# data_manager.py
# (请完全覆盖原文件)

import sqlite3
import pandas as pd
from datetime import datetime, timedelta

DB_FILE = 'investments.db'


def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # 1. 交易表 (统一使用 note 单数)
    c.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            symbol TEXT NOT NULL,
            type TEXT NOT NULL, 
            quantity REAL NOT NULL,
            price REAL NOT NULL,
            fee REAL DEFAULT 0,
            note TEXT, 
            is_deleted INTEGER DEFAULT 0,
            deleted_at TEXT
        )
    ''')

    # 2. 资金流水表
    c.execute('''
        CREATE TABLE IF NOT EXISTS funds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            type TEXT NOT NULL,
            amount REAL NOT NULL,
            note TEXT
        )
    ''')

    # 3. 每日净值快照表
    c.execute('''
        CREATE TABLE IF NOT EXISTS daily_snapshots (
            date TEXT PRIMARY KEY,
            total_asset REAL,
            total_cost REAL,
            total_pnl REAL
        )
    ''')
    conn.commit()
    conn.close()

    # 检查 schema 防止旧版兼容问题
    check_and_migrate_schema()


def check_and_migrate_schema():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    try:
        c.execute("SELECT is_deleted FROM transactions LIMIT 1")
    except sqlite3.OperationalError:
        # 如果是旧版DB，追加列
        try:
            c.execute("ALTER TABLE transactions ADD COLUMN is_deleted INTEGER DEFAULT 0")
            c.execute("ALTER TABLE transactions ADD COLUMN deleted_at TEXT")
            conn.commit()
        except:
            pass
    conn.close()


# --- 交易相关 ---
def add_transaction(date, symbol, trans_type, quantity, price, fee, note):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        INSERT INTO transactions (date, symbol, type, quantity, price, fee, note, is_deleted) 
        VALUES (?, ?, ?, ?, ?, ?, ?, 0)
    ''', (date, symbol.upper(), trans_type, quantity, price, fee, note))
    conn.commit()
    conn.close()


def soft_delete_transaction(trans_id):
    """软删除：标记为已删除"""
    # 关键修复：强制转换 ID 为原生 int，防止 numpy.int64 导致 sqlite 匹配失败
    trans_id = int(trans_id)

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 执行更新
    c.execute('UPDATE transactions SET is_deleted = 1, deleted_at = ? WHERE id = ?', (now, trans_id))
    conn.commit()

    # 调试信息：确认是否真的更新了
    if c.rowcount == 0:
        print(f"⚠️ Warning: No rows deleted for ID {trans_id}")
    else:
        print(f"✅ Soft deleted ID {trans_id}")

    conn.close()


def restore_transaction(trans_id):
    trans_id = int(trans_id)  # 类型安全转换
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('UPDATE transactions SET is_deleted = 0, deleted_at = NULL WHERE id = ?', (trans_id,))
    conn.commit()
    conn.close()


def get_all_transactions(include_deleted=False):
    conn = sqlite3.connect(DB_FILE)
    query = "SELECT * FROM transactions"
    if not include_deleted:
        query += " WHERE is_deleted = 0 OR is_deleted IS NULL"

    query += " ORDER BY date DESC, id DESC"
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df


def get_deleted_transactions_last_7_days():
    conn = sqlite3.connect(DB_FILE)
    seven_days_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    query = f"SELECT * FROM transactions WHERE is_deleted = 1 AND deleted_at >= '{seven_days_ago}' ORDER BY deleted_at DESC"
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df


# --- 资金相关 ---
def add_fund_flow(date, f_type, amount, note):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('INSERT INTO funds (date, type, amount, note) VALUES (?, ?, ?, ?)', (date, f_type, amount, note))
    conn.commit()
    conn.close()


def get_total_invested():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    try:
        c.execute("SELECT type, sum(amount) FROM funds GROUP BY type")
        rows = c.fetchall()
    except:
        return 0
    conn.close()
    total = 0
    for r in rows:
        if r[0] == 'DEPOSIT':
            total += r[1]
        elif r[0] == 'WITHDRAW':
            total -= r[1]
    return total


# --- 历史快照相关 ---
def save_daily_snapshot(date_str, asset, cost):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    pnl = asset - cost
    c.execute('INSERT OR REPLACE INTO daily_snapshots (date, total_asset, total_cost, total_pnl) VALUES (?, ?, ?, ?)',
              (date_str, asset, cost, pnl))
    conn.commit()
    conn.close()


def get_history_data():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM daily_snapshots ORDER BY date ASC", conn)
    conn.close()
    return df


# --- 持仓计算 ---
def get_portfolio_summary():
    df = get_all_transactions(include_deleted=False)
    if df.empty: return pd.DataFrame()

    df = df.sort_values(by=['date', 'id'])
    portfolio = {}

    for _, row in df.iterrows():
        sym = row['symbol']
        if sym not in portfolio:
            portfolio[sym] = {'quantity': 0, 'total_cost': 0}

        if row['type'] == 'BUY':
            portfolio[sym]['quantity'] += row['quantity']
            portfolio[sym]['total_cost'] += (row['price'] * row['quantity'] + row['fee'])
        elif row['type'] == 'SELL':
            if portfolio[sym]['quantity'] > 0:
                avg_cost = portfolio[sym]['total_cost'] / portfolio[sym]['quantity']
                portfolio[sym]['total_cost'] -= (avg_cost * row['quantity'])
                portfolio[sym]['quantity'] -= row['quantity']

    res = []
    for sym, data in portfolio.items():
        if data['quantity'] > 0.001:
            current_qty = data['quantity']
            total_c = data['total_cost']
            avg_c = total_c / current_qty if current_qty > 0 else 0

            res.append({
                'Symbol': sym,
                'Quantity': current_qty,
                'Avg Cost': avg_c,
                'Total Cost': total_c
            })

    return pd.DataFrame(res)