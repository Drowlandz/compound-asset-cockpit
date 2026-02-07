#!/usr/bin/env python3
"""
更新股票现价脚本
功能：
- 自动获取当前持有的股票列表（排除 OPTION 和已删除）
- 支持单独更新或批量更新股票现价
- 跳过 OPTION 类型（无法获取实时价格）

用法:
  python3 update_price.py AMZN 8.55                    # 更新单个股票
  python3 update_price.py --update-all                 # 批量更新所有持仓
  python3 update_price.py --list-holdings              # 查看当前持仓
"""

import sqlite3
import sys
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "investments.db")


def get_holdings():
    """获取当前持有的股票列表（排除 OPTION 和已删除）"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 获取所有未删除的交易
    cursor.execute("""
        SELECT symbol, asset_category, SUM(quantity) as qty
        FROM transactions 
        WHERE is_deleted = 0 AND asset_category != 'OPTION'
        GROUP BY symbol
        HAVING qty > 0
    """)
    
    holdings = []
    for row in cursor.fetchall():
        holdings.append({
            'symbol': row[0],
            'category': row[1],
            'quantity': row[2]
        })
    
    conn.close()
    return holdings


def get_option_symbols():
    """获取所有 OPTION 类型的股票代码（这些不需要更新）"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT DISTINCT symbol 
        FROM transactions 
        WHERE asset_category = 'OPTION' AND is_deleted = 0
    """)
    
    options = [row[0] for row in cursor.fetchall()]
    conn.close()
    return options


def init_price_table():
    """初始化现价表（包含 asset_category）"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 检查是否存在 asset_category 列
    cursor.execute("PRAGMA table_info(stock_prices)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'asset_category' not in columns:
        cursor.execute('ALTER TABLE stock_prices ADD COLUMN asset_category TEXT')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stock_prices (
            symbol TEXT PRIMARY KEY,
            current_price REAL,
            price_source TEXT,
            updated_at TEXT,
            asset_category TEXT
        )
    ''')
    
    conn.commit()
    conn.close()


def update_stock_price(symbol, new_price, source='manual', force=False, asset_category='STOCK'):
    """更新单个股票的现价
    
    Args:
        symbol: 股票代码
        new_price: 新价格
        source: 价格来源 ('manual' 或 'auto')
        force: 是否强制更新（用于手动设定期权价格）
        asset_category: 资产类别 ('STOCK' 或 'OPTION')
    """
    # 检查是否是期权
    is_option = asset_category == 'OPTION' or symbol.startswith('OPT:') or ' ' in symbol or symbol.upper().endswith('CALL') or symbol.upper().endswith('PUT')
    
    # 跳过期权（除非 force=True 或已指定 asset_category=OPTION）
    if is_option and not force:
        print(f"⏭️  跳过 {symbol} (OPTION 类型，使用 --manual 强制更新)")
        return False
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute('''
        INSERT OR REPLACE INTO stock_prices (symbol, current_price, price_source, updated_at, asset_category)
        VALUES (?, ?, ?, ?, ?)
    ''', (symbol.upper(), float(new_price), source, now, asset_category))
    
    conn.commit()
    conn.close()
    
    print(f"✅ {symbol.upper()} = ${float(new_price):.2f} ({asset_category})")
    return True


def update_all_holdings(prices_dict, source='manual'):
    """批量更新所有持仓股票的价格
    
    Args:
        prices_dict: 股票代码到价格的字典 {'AAPL': 150.00, 'NVDA': 500.00}
        source: 价格来源标识
    """
    init_price_table()
    
    holdings = get_holdings()
    options = get_option_symbols()
    
    print(f"\n📊 开始更新持仓股价...")
    print(f"   持仓数量: {len(holdings)}")
    print(f"   需跳过 OPTION: {len(options)} 个\n")
    
    updated = 0
    skipped = 0
    not_found = []
    
    for stock in holdings:
        symbol = stock['symbol']
        category = stock['category']
        
        # 检查是否是 OPTION 相关
        if category == 'OPTION' or symbol in options:
            print(f"⏭️  跳过 {symbol} (OPTION 类型)")
            skipped += 1
            continue
        
        # 更新价格
        if symbol in prices_dict:
            if update_stock_price(symbol, prices_dict[symbol], source):
                updated += 1
        else:
            print(f"❓ {symbol} - 未提供价格")
            not_found.append(symbol)
    
    print(f"\n📈 更新完成:")
    print(f"   ✅ 成功更新: {updated}")
    print(f"   ⏭️  跳过: {skipped}")
    if not_found:
        print(f"   ⚠️  未提供价格: {', '.join(not_found)}")
    
    return updated > 0


def list_holdings():
    """列出当前所有持仓"""
    holdings = get_holdings()
    options = get_option_symbols()
    
    print("\n📊 当前持仓列表 (排除 OPTION):")
    print("-" * 50)
    
    if not holdings:
        print("   暂无持仓")
        return
    
    for stock in holdings:
        symbol = stock['symbol']
        qty = stock['quantity']
        category = stock['category']
        print(f"   {symbol:10} | {qty:8.2f} 股 | {category}")
    
    print("-" * 50)
    print(f"   共 {len(holdings)} 个持仓")
    
    if options:
        print(f"\n⏭️  OPTION 类型 (已跳过):")
        for opt in options:
            print(f"   • {opt}")


def view_current_prices():
    """查看当前保存的股价"""
    init_price_table()
    
    conn = sqlite3.connect(DB_PATH)
    
    # 获取所有持仓的现价（包含 asset_category）
    df = pd.read_sql_query("""
        SELECT sp.symbol, sp.current_price, sp.price_source, sp.updated_at,
               COALESCE(t.qty, 0) as quantity, COALESCE(t.category, 'UNKNOWN') as category
        FROM stock_prices sp
        LEFT JOIN (
            SELECT symbol, SUM(quantity) as qty, asset_category as category
            FROM transactions 
            WHERE is_deleted = 0
            GROUP BY symbol
        ) t ON sp.symbol = t.symbol
        WHERE COALESCE(t.qty, 0) > 0
        ORDER BY sp.updated_at DESC
    """, conn)
    conn.close()
    
    if df.empty:
        print("\n📭 暂无股价数据")
        return
    
    # 分离 STOCK 和 OPTION
    stocks = df[df['category'] != 'OPTION']
    options = df[df['category'] == 'OPTION']
    
    print("\n📈 当前持仓股价:")
    print("-" * 70)
    print(f"   {'代码':10} | {'现价':>10} | {'数量':>8} | {'市值':>15} | {'类型'}")
    print("-" * 70)
    
    total_value = 0
    
    # STOCK
    for _, row in stocks.iterrows():
        price = row['current_price']
        qty = row['quantity']
        value = price * qty if price else 0
        price_str = f"${price:,.2f}" if price else "N/A"
        source = "(自动)" if row['price_source'] == 'auto' else ""
        total_value += value
        print(f"   {row['symbol']:10} | {price_str:>10} | {qty:8.2f} | ${value:>14,.2f} | STOCK {source}")
    
    # OPTION
    for _, row in options.iterrows():
        price = row['current_price']
        qty = row['quantity']
        value = price * qty if price else 0
        price_str = f"${price:,.2f}" if price else "❌ 未设定"
        source = "(手动)" if row['price_source'] == 'manual' else ""
        total_value += value
        print(f"   {row['symbol']:10} | {price_str:>10} | {qty:8.2f} | ${value:>14,.2f} | OPTION {source}")
    
    print("-" * 70)
    print(f"   {'总计':38} | ${total_value:>14,.2f}")
    
    # 提示未设定价格的 OPTION
    unset_options = options[options['current_price'].isna()]
    if not unset_options.empty:
        print(f"\n⚠️  以下 OPTION 未设定现价:")
        for _, row in unset_options.iterrows():
            print(f"   • {row['symbol']} ({row['quantity']:.0f} 股)")
        print(f"\n💡 提示: 使用 python3 update_price.py '{row['symbol']} 8.55' 设定现价")


def reset_prices():
    """清空所有股价数据"""
    init_price_table()
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM stock_prices")
    conn.commit()
    conn.close()
    print("✅ 已清空所有股价数据")


if __name__ == "__main__":
    import pandas as pd
    
    if len(sys.argv) == 1:
        print("用法:")
        print("  python3 update_price.py AMZN 8.55                   # 更新单个股票")
        print("  python3 update_price.py --list                      # 查看持仓列表")
        print("  python3 update_price.py --prices                    # 查看当前股价")
        print("  python3 update_price.py --reset                     # 清空股价数据")
        print("  python3 update_price.py --manual 'AMZN 2026-02-07 CALL' 8.55  # 手动设定期权价格")
        print("\n批量更新示例:")
        print("  python3 update_price.py --batch AAPL 150 NVDA 500 MSFT 380")
        
    elif sys.argv[1] == '--list':
        list_holdings()
        
    elif sys.argv[1] == '--prices':
        view_current_prices()
        
    elif sys.argv[1] == '--reset':
        confirm = input("确认清空所有股价数据? (y/n): ")
        if confirm.lower() == 'y':
            reset_prices()
        else:
            print("已取消")
            
    elif sys.argv[1] == '--manual':
        # 手动更新（支持期权）: python3 update_price.py --manual 'AMZN 2026-02-07 CALL' 8.55
        if len(sys.argv) < 4:
            print("❌ 需要提供股票代码和价格")
            print("用法: python3 update_price.py --manual 'AMZN 2026-02-07 CALL' 8.55")
        else:
            symbol = sys.argv[2]
            price = sys.argv[3]
            init_price_table()
            update_stock_price(symbol, price, force=True)
            
    elif sys.argv[1] == '--batch':
        # 批量更新: python3 update_price.py --batch AAPL 150 NVDA 500
        if len(sys.argv) < 4:
            print("❌ 批量更新需要提供至少一个股票和价格")
            print("用法: python3 update_price.py --batch AAPL 150 NVDA 500")
        else:
            prices = {}
            i = 2
            while i < len(sys.argv):
                symbol = sys.argv[i]
                price = sys.argv[i + 1]
                prices[symbol] = price
                i += 2
            update_all_holdings(prices)
            
    elif len(sys.argv) >= 3:
        # 单个更新: python3 update_price.py AMZN 8.55
        symbol = sys.argv[1]
        price = sys.argv[2]
        init_price_table()
        update_stock_price(symbol, price)
        
    elif len(sys.argv) == 2:
        # 只提供股票，交互式输入
        symbol = sys.argv[1]
        price = input(f"请输入 {symbol.upper()} 的新价格: ")
        if price:
            init_price_table()
            update_stock_price(symbol, price)
        else:
            print("未输入价格，操作取消")
