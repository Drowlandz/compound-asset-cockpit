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

    # 1. 交易表
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

    # 2. 资金流水表
    c.execute('''CREATE TABLE IF NOT EXISTS fund_flows (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        type TEXT NOT NULL,
        amount REAL NOT NULL,
        note TEXT
    )''')

    # 3. 每日快照表
    c.execute('''CREATE TABLE IF NOT EXISTS daily_snapshots (
        date TEXT PRIMARY KEY,
        total_asset REAL,
        total_invested REAL
    )''')

    # 4. 现金余额表
    c.execute('''CREATE TABLE IF NOT EXISTS cash_balance (
        id INTEGER PRIMARY KEY,
        balance REAL DEFAULT 0
    )''')
    c.execute("INSERT OR IGNORE INTO cash_balance (id, balance) VALUES (1, 0)")

    # 5. 🔥 新增：宏观数据缓存表 (Key-Value)
    c.execute('''CREATE TABLE IF NOT EXISTS macro_cache (
        key TEXT PRIMARY KEY, -- vix, tnx, cnh...
        value REAL,
        updated_at TEXT
    )''')

    # 6. 🔥 新增：股票元数据缓存表 (Symbol-Meta)
    # 赛道信息几乎不怎么变，存本地可以极大加速
    c.execute('''CREATE TABLE IF NOT EXISTS stock_meta (
        symbol TEXT PRIMARY KEY,
        sector TEXT,
        currency TEXT,
        updated_at TEXT
    )''')

    # 7. 现价缓存表 (确保主程序可用)
    c.execute('''
        CREATE TABLE IF NOT EXISTS stock_prices (
            symbol TEXT PRIMARY KEY,
            current_price REAL,
            price_source TEXT,
            updated_at TEXT,
            asset_category TEXT
        )
    ''')

    # 兼容旧表结构：补 asset_category 列
    c.execute("PRAGMA table_info(stock_prices)")
    columns = [col[1] for col in c.fetchall()]
    if 'asset_category' not in columns:
        c.execute('ALTER TABLE stock_prices ADD COLUMN asset_category TEXT')

    # 自动修复/迁移
    try:
        c.execute("SELECT total_invested FROM daily_snapshots LIMIT 1")
    except sqlite3.OperationalError:
        c.execute("ALTER TABLE daily_snapshots ADD COLUMN total_invested REAL DEFAULT 0")

    conn.commit()
    conn.close()


# ================= 缓存读写 (新增模块) =================

def update_macro_cache(key, value):
    """更新宏观数据缓存"""
    if value is None: return
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT OR REPLACE INTO macro_cache (key, value, updated_at) VALUES (?, ?, ?)", (key, value, now))
    conn.commit()
    conn.close()


def get_macro_cache(key):
    """读取宏观数据缓存"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT value FROM macro_cache WHERE key=?", (key,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None


def update_stock_meta(symbol, sector, currency='USD'):
    """更新股票元数据 (赛道/币种)"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT OR REPLACE INTO stock_meta (symbol, sector, currency, updated_at) VALUES (?, ?, ?, ?)",
              (symbol, sector, currency, now))
    conn.commit()
    conn.close()


def get_stock_meta(symbol):
    """读取股票元数据"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT sector, currency FROM stock_meta WHERE symbol=?", (symbol,))
    row = c.fetchone()
    conn.close()
    if row:
        return {'sector': row[0], 'currency': row[1]}
    return None


# ================= 交易部分 (保持不变) =================

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


def get_stock_holdings_for_sell():
    """仅返回股票(STOCK)的可卖持仓，避免把期权混入股票卖出列表。"""
    df = get_all_transactions(include_deleted=False)
    if df.empty:
        return pd.DataFrame(columns=['Symbol', 'Quantity'])

    df = df[df['asset_category'] == 'STOCK'].copy()
    if df.empty:
        return pd.DataFrame(columns=['Symbol', 'Quantity'])

    df['signed_qty'] = df.apply(
        lambda r: float(r['quantity']) if r['type'] == 'BUY' else -float(r['quantity']),
        axis=1
    )
    summary = df.groupby('symbol', as_index=False)['signed_qty'].sum()
    summary = summary[summary['signed_qty'] > 0.01].copy()
    summary.rename(columns={'symbol': 'Symbol', 'signed_qty': 'Quantity'}, inplace=True)
    return summary.sort_values('Symbol').reset_index(drop=True)


def get_open_option_positions():
    """返回当前仍持有的期权合约持仓（按 symbol+expiration+option_type+strike 聚合）。"""
    df = get_all_transactions(include_deleted=False)
    if df.empty:
        return pd.DataFrame(columns=['symbol', 'expiration', 'option_type', 'strike', 'quantity'])

    df = df[df['asset_category'] == 'OPTION'].copy()
    if df.empty:
        return pd.DataFrame(columns=['symbol', 'expiration', 'option_type', 'strike', 'quantity'])

    df['signed_qty'] = df.apply(
        lambda r: float(r['quantity']) if r['type'] == 'BUY' else -float(r['quantity']),
        axis=1
    )

    grouped = (
        df.groupby(['symbol', 'expiration', 'option_type', 'strike'], as_index=False, dropna=False)['signed_qty']
        .sum()
    )
    grouped = grouped[grouped['signed_qty'] > 0.01].copy()
    grouped.rename(columns={'signed_qty': 'quantity'}, inplace=True)
    return grouped.sort_values(['symbol', 'expiration', 'option_type', 'strike']).reset_index(drop=True)


def build_option_price_symbol(symbol, expiration, option_type, strike=None):
    """构建期权价格缓存键，优先包含 strike，避免同到期同方向不同执行价冲突。"""
    sym = str(symbol).upper().strip()
    exp = str(expiration).strip()
    o_type = str(option_type).upper().strip()

    if strike is None or str(strike).strip() == "":
        return f"{sym} {exp} {o_type}"

    try:
        strike_txt = f"{float(strike):g}"
    except (TypeError, ValueError):
        strike_txt = str(strike).strip()
    return f"{sym} {exp} {o_type} {strike_txt}"


def upsert_stock_price(symbol, current_price, source='manual', asset_category='STOCK'):
    """写入/更新 stock_prices 表。"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute(
        '''
        INSERT OR REPLACE INTO stock_prices (symbol, current_price, price_source, updated_at, asset_category)
        VALUES (?, ?, ?, ?, ?)
        ''',
        (str(symbol).upper().strip(), float(current_price), source, now, asset_category)
    )
    conn.commit()
    conn.close()


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
                'Days Held': 0, 'First Buy Date': None,
                # 期权合约元数据（用于按合约查现价）
                'expiration': row['expiration'] if row['asset_category'] == 'OPTION' else None,
                'option_type': row['option_type'] if row['asset_category'] == 'OPTION' else None,
                'strike': row['strike'] if row['asset_category'] == 'OPTION' else None,
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

        # 若为期权，尽量补齐合约元数据，避免估值查不到对应期权现价
        if p['Type'] == 'OPTION':
            if p.get('expiration') in (None, '') and row.get('expiration') not in (None, ''):
                p['expiration'] = row.get('expiration')
            if p.get('option_type') in (None, '') and row.get('option_type') not in (None, ''):
                p['option_type'] = row.get('option_type')
            if p.get('strike') in (None, '') and row.get('strike') not in (None, ''):
                p['strike'] = row.get('strike')

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


# ================= 资金管理 (保持不变) =================

def manage_principal(date, p_type, amount, note):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO fund_flows (date, type, amount, note) VALUES (?, ?, ?, ?)", (date, p_type, amount, note))
    change = amount if p_type == 'DEPOSIT' else -amount
    c.execute("UPDATE cash_balance SET balance = balance + ? WHERE id = 1", (change,))
    conn.commit()
    conn.close()


def reset_principal_only(amount, date_str):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM fund_flows")
    c.execute("INSERT INTO fund_flows (date, type, amount, note) VALUES (?, 'RESET', ?, '本金基准重置')",
              (date_str, amount))
    conn.commit()
    conn.close()


def delete_fund_flow(f_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT type, amount FROM fund_flows WHERE id=?", (f_id,))
    row = c.fetchone()
    if row:
        f_type, amt = row
        if f_type in ['DEPOSIT', 'WITHDRAW']:
            rollback = -amt if f_type == 'DEPOSIT' else amt
            c.execute("UPDATE cash_balance SET balance = balance + ? WHERE id = 1", (rollback,))
    c.execute("DELETE FROM fund_flows WHERE id=?", (f_id,))
    conn.commit()
    conn.close()


def get_total_invested():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
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
