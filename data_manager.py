import sqlite3
import pandas as pd
import sys
import os
from datetime import datetime, timedelta

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_FILE = os.path.join(BASE_DIR, "investments.db")

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # 1. 交易表 (基础结构)
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
            deleted_at TEXT,
            asset_category TEXT DEFAULT 'STOCK', -- 新增: STOCK 或 OPTION
            multiplier INTEGER DEFAULT 1,        -- 新增: 乘数(股票1, 期权100)
            strike REAL,                         -- 新增: 行权价
            expiration TEXT,                     -- 新增: 到期日
            option_type TEXT                     -- 新增: CALL/PUT
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

    # === 数据库自动迁移 (Schema Migration) ===
    check_and_migrate_schema()


def check_and_migrate_schema():
    """检查并自动添加缺失的列"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    columns_to_add = {
        'is_deleted': 'INTEGER DEFAULT 0',
        'deleted_at': 'TEXT',
        'asset_category': "TEXT DEFAULT 'STOCK'",
        'multiplier': 'INTEGER DEFAULT 1',
        'strike': 'REAL',
        'expiration': 'TEXT',
        'option_type': 'TEXT'
    }

    try:
        # 获取现有列名
        c.execute("PRAGMA table_info(transactions)")
        existing_cols = [row[1] for row in c.fetchall()]

        for col, dtype in columns_to_add.items():
            if col not in existing_cols:
                print(f"Migrating DB: Adding column '{col}'...")
                c.execute(f"ALTER TABLE transactions ADD COLUMN {col} {dtype}")

        conn.commit()
    except Exception as e:
        print(f"Migration Warning: {e}")
    finally:
        conn.close()


# --- 交易相关 ---
def add_transaction(date, symbol, trans_type, quantity, price, fee, note,
                    asset_category='STOCK', multiplier=1, strike=None, expiration=None, option_type=None):
    """通用的交易添加函数，支持股票和期权"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        INSERT INTO transactions (
            date, symbol, type, quantity, price, fee, note, is_deleted, 
            asset_category, multiplier, strike, expiration, option_type
        ) 
        VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?)
    ''', (date, symbol.upper(), trans_type, quantity, price, fee, note,
          asset_category, multiplier, strike, expiration, option_type))
    conn.commit()
    conn.close()


def soft_delete_transaction(trans_id):
    trans_id = int(trans_id)
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute('UPDATE transactions SET is_deleted = 1, deleted_at = ? WHERE id = ?', (now, trans_id))
    conn.commit()
    conn.close()


def restore_transaction(trans_id):
    trans_id = int(trans_id)
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
    """计算净投入本金 (入金 - 出金)"""
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


def get_cash_balance():
    """
    核心功能：计算账户浮存金
    公式 = (总入金 - 总出金) + (卖出获得资金 - 买入花费资金)
    注意：包含股票和期权，考虑了 multiplier (股票1, 期权100) 和 手续费
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # 1. 资金进出
    c.execute("SELECT type, sum(amount) FROM funds GROUP BY type")
    fund_rows = c.fetchall()
    fund_balance = 0
    for r in fund_rows:
        if r[0] == 'DEPOSIT':
            fund_balance += r[1]
        elif r[0] == 'WITHDRAW':
            fund_balance -= r[1]

    # 2. 交易产生的现金流 (只计算未删除的记录)
    # BUY: 流出 = price * qty * multiplier + fee
    # SELL: 流入 = price * qty * multiplier - fee
    query = """
        SELECT type, sum(price * quantity * multiplier), sum(fee)
        FROM transactions 
        WHERE is_deleted = 0 OR is_deleted IS NULL
        GROUP BY type
    """
    c.execute(query)
    trade_rows = c.fetchall()

    trade_cash_flow = 0
    for r in trade_rows:
        t_type = r[0]
        t_amount = r[1] if r[1] else 0
        t_fee = r[2] if r[2] else 0

        if t_type == 'BUY':
            trade_cash_flow -= (t_amount + t_fee)
        elif t_type == 'SELL':
            trade_cash_flow += (t_amount - t_fee)

    conn.close()

    return fund_balance + trade_cash_flow


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


def get_portfolio_summary():
    """获取持仓列表（含股票和期权）- 升级版：增加持仓天数"""
    df = get_all_transactions(include_deleted=False)
    if df.empty: return pd.DataFrame()

    df = df.sort_values(by=['date', 'id'])
    portfolio = {}

    for _, row in df.iterrows():
        raw_sym = row['symbol']
        is_option = row.get('asset_category') == 'OPTION'

        if is_option:
            key = f"{raw_sym} {row['expiration']} {row['option_type']} {row['strike']}"
        else:
            key = raw_sym

        if key not in portfolio:
            portfolio[key] = {
                'symbol': raw_sym,
                'quantity': 0,
                'total_cost': 0,
                'multiplier': row.get('multiplier', 1),
                'type': row.get('asset_category', 'STOCK'),
                'first_buy_date': None  # 新增：首次买入日期
            }

        multiplier = row.get('multiplier', 1)

        if row['type'] == 'BUY':
            portfolio[key]['quantity'] += row['quantity']
            portfolio[key]['total_cost'] += (row['price'] * row['quantity'] * multiplier + row['fee'])

            # 记录最早买入时间
            if portfolio[key]['first_buy_date'] is None:
                portfolio[key]['first_buy_date'] = row['date']

        elif row['type'] == 'SELL':
            if portfolio[key]['quantity'] > 0:
                avg_cost = portfolio[key]['total_cost'] / portfolio[key]['quantity']
                portfolio[key]['total_cost'] -= (avg_cost * row['quantity'])
                portfolio[key]['quantity'] -= row['quantity']

    # 清理已清仓的记录
    res = []
    today = datetime.now().date()

    for key, data in portfolio.items():
        if data['quantity'] > 0.001:
            current_qty = data['quantity']
            total_c = data['total_cost']
            divisor = current_qty * data['multiplier']
            avg_c = total_c / divisor if divisor > 0 else 0

            # 计算持仓天数
            days_held = 0
            if data['first_buy_date']:
                try:
                    f_date = datetime.strptime(data['first_buy_date'], "%Y-%m-%d").date()
                    days_held = (today - f_date).days
                except:
                    days_held = 0

            res.append({
                'Symbol': key,
                'Raw Symbol': data['symbol'],
                'Quantity': current_qty,
                'Avg Cost': avg_c,
                'Total Cost': total_c,
                'Type': data['type'],
                'Multiplier': data['multiplier'],
                'Days Held': days_held  # 新增字段
            })

    return pd.DataFrame(res)


def set_cash_balance(target_amount, date_str):
    """
    通过插入一条差额流水，将当前浮存金强行校准为目标金额。
    原理：差额 = 目标 - 当前。
    """
    # 1. 获取当前理论余额
    current = get_cash_balance()

    # 2. 计算差额
    diff = target_amount - current

    # 3. 如果差额非常小，忽略
    if abs(diff) < 0.01:
        return

    # 4. 判断是需要补钱(DEPOSIT)还是扣钱(WITHDRAW)
    if diff > 0:
        f_type = 'DEPOSIT'
        note = f"余额校准：系统自动补入 (原: {current:,.2f})"
    else:
        f_type = 'WITHDRAW'
        note = f"余额校准：系统自动扣除 (原: {current:,.2f})"

    # 5. 写入修正记录
    add_fund_flow(date_str, f_type, abs(diff), note)

def get_fund_flows(include_calib=False):
    """
    获取资金流水
    :param include_calib: False=只看入金出金, True=包含系统校准记录
    """
    conn = sqlite3.connect(DB_FILE)

    # 基础语句
    sql = "SELECT * FROM funds"

    # 修正逻辑：使用白名单机制 (只显示入金和出金)，并确保 SQL 语句空格正确
    if not include_calib:
        sql += " WHERE type IN ('DEPOSIT', 'WITHDRAW')"

    sql += " ORDER BY date DESC, id DESC"

    try:
        df = pd.read_sql_query(sql, conn)
    except Exception as e:
        print(f"SQL Error: {e}")
        df = pd.DataFrame()  # 出错返回空表防止崩坏
    finally:
        conn.close()

    return df


def delete_fund_flow(fund_id):
    """删除资金记录"""
    # 修正逻辑：强制转为 int，防止 numpy 类型导致 SQLite 删除失败
    try:
        f_id = int(fund_id)
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("DELETE FROM funds WHERE id = ?", (f_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Delete Error: {e}")
        return False

def add_fund_flow(date, f_type, amount, note):
    """记录资金流水"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('INSERT INTO funds (date, type, amount, note) VALUES (?, ?, ?, ?)', (date, f_type, amount, note))
    conn.commit()
    conn.close()


def get_total_invested():
    """
    计算总投入本金 (仅包含入金和出金，排除校准/分红等杂项)
    用于计算收益率的分母。
    """
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
        f_type, amount = r[0], r[1]
        # 只有明确的入金和出金才算作本金变化
        if f_type == 'DEPOSIT':
            total += amount
        elif f_type == 'WITHDRAW':
            total -= amount
        # CALIB_ADD / CALIB_SUB 被忽略
    return total


def get_cash_balance():
    """
    计算账户浮存金 (Cash Balance)
    公式: (所有资金流入 - 所有资金流出) + (卖出总额 - 买入总额 - 手续费)
    """
    # 1. 计算资金账户的净额 (包含本金 + 校准差额)
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT type, sum(amount) FROM funds GROUP BY type")
    rows = c.fetchall()
    conn.close()

    fund_net = 0
    for r in rows:
        f_type, amount = r[0], r[1]
        if f_type in ['DEPOSIT', 'CALIB_ADD']:  # 入金 或 校准增加
            fund_net += amount
        elif f_type in ['WITHDRAW', 'CALIB_SUB']:  # 出金 或 校准减少
            fund_net -= amount

    # 2. 计算交易账户的现金流 (盈亏/买卖)
    df_trans = get_all_transactions(include_deleted=False)
    trading_cash_flow = 0

    if not df_trans.empty:
        for _, row in df_trans.iterrows():
            # 兼容期权和股票：Price * Qty * Multiplier
            # 如果是旧数据没有 multiplier 列，默认为1
            mult = row.get('multiplier', 1)
            if pd.isna(mult): mult = 1

            total_amount = row['price'] * row['quantity'] * mult

            if row['type'] == 'BUY':
                trading_cash_flow -= (total_amount + row['fee'])
            elif row['type'] == 'SELL':
                trading_cash_flow += (total_amount - row['fee'])

    return fund_net + trading_cash_flow


def set_cash_balance(target_amount, date_str):
    """
    余额校准 (修正版)
    使用特殊的 CALIB 类型，只调整余额，不影响本金投入。
    """
    current = get_cash_balance()
    diff = target_amount - current

    if abs(diff) < 0.01: return

    if diff > 0:
        # 余额少了，需要增加 (类似分红或利息)
        f_type = 'CALIB_ADD'
        note = f"余额校准 (增加): {current:,.2f} -> {target_amount:,.2f}"
    else:
        # 余额多了，需要减少 (类似扣费)
        f_type = 'CALIB_SUB'
        note = f"余额校准 (扣除): {current:,.2f} -> {target_amount:,.2f}"

    add_fund_flow(date_str, f_type, abs(diff), note)