import sqlite3
import pandas as pd
from datetime import datetime

DB_FILE = 'investments.db'


def init_db():
    """初始化数据库，如果不存在则创建"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # 创建交易表
    c.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            symbol TEXT NOT NULL,
            type TEXT NOT NULL,  -- 'BUY' or 'SELL'
            quantity REAL NOT NULL,
            price REAL NOT NULL,
            fee REAL DEFAULT 0,
            note TEXT
        )
    ''')
    conn.commit()
    conn.close()


def add_transaction(date, symbol, trans_type, quantity, price, fee, note):
    """添加一条交易记录"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        INSERT INTO transactions (date, symbol, type, quantity, price, fee, note)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (date, symbol.upper(), trans_type, quantity, price, fee, note))
    conn.commit()
    conn.close()


def get_all_transactions():
    """获取所有交易记录，返回 DataFrame"""
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM transactions ORDER BY date DESC", conn)
    conn.close()
    return df


def get_portfolio_summary():
    """
    计算当前持仓。
    逻辑：买入加数量，卖出减数量，计算加权平均成本。
    注意：这是简化版逻辑，暂不处理复杂的卖出分批结转成本。
    """
    df = get_all_transactions()
    if df.empty:
        return pd.DataFrame()

    portfolio = {}

    for _, row in df.iterrows():
        sym = row['symbol']
        if sym not in portfolio:
            portfolio[sym] = {'quantity': 0, 'total_cost': 0}

        if row['type'] == 'BUY':
            portfolio[sym]['quantity'] += row['quantity']
            # 成本 = 价格 * 数量 + 手续费
            portfolio[sym]['total_cost'] += (row['price'] * row['quantity'] + row['fee'])
        elif row['type'] == 'SELL':
            # 卖出时简单处理：按比例减少总成本（保持平均成本不变）
            if portfolio[sym]['quantity'] > 0:
                cost_per_share = portfolio[sym]['total_cost'] / portfolio[sym]['quantity']
                portfolio[sym]['quantity'] -= row['quantity']
                portfolio[sym]['total_cost'] -= (cost_per_share * row['quantity'])

    # 转换为 DataFrame
    res = []
    for sym, data in portfolio.items():
        if data['quantity'] > 0.001:  # 过滤掉已清仓的
            avg_cost = data['total_cost'] / data['quantity']
            res.append({
                'Symbol': sym,
                'Quantity': data['quantity'],
                'Avg Cost': round(avg_cost, 3),
                'Total Cost': round(data['total_cost'], 2)
            })

    return pd.DataFrame(res)