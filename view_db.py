#!/usr/bin/env python3
"""
数据库数据查看脚本
展示 investments.db 中所有表的数据，带有格式化输出
"""

import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "investments.db")


def print_header(title):
    """打印带格式的标题"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_table_data(df, title, index=False):
    """格式化打印表格数据"""
    print_header(title)
    if df.empty:
        print("  📭 数据为空")
        return
    
    # 根据数据类型调整列宽
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', None)
    pd.set_option('display.max_colwidth', 20)
    
    print(df.to_string(index=index))
    print(f"\n  📊 共 {len(df)} 条记录")


def get_table_info(cursor, table_name):
    """获取表的字段信息"""
    cursor.execute(f"PRAGMA table_info({table_name})")
    return cursor.fetchall()


def get_table_count(cursor, table_name):
    """获取表的数据条数"""
    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    return cursor.fetchone()[0]


def view_all_data():
    """查看所有表的数据"""
    if not os.path.exists(DB_PATH):
        print(f"❌ 数据库不存在: {DB_PATH}")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print(f"\n🔍 数据库: {DB_PATH}")
    print(f"⏰ 查阅时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 获取所有表名
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = cursor.fetchall()
    
    if not tables:
        print("📭 数据库中没有表")
        conn.close()
        return
    
    print(f"\n📋 数据库包含 {len(tables)} 个表:")
    for table in tables:
        count = get_table_count(cursor, table[0])
        print(f"   • {table[0]} ({count} 条)")
    
    # 逐个展示表数据
    for table in tables:
        table_name = table[0]
        
        # 特殊处理缓存表
        if table_name == 'macro_cache':
            # 宏观数据缓存表
            df = pd.read_sql_query("SELECT * FROM macro_cache ORDER BY key", conn)
            print_header("💾 宏观数据缓存 - macro_cache")
            if df.empty:
                print("  📭 数据为空")
            else:
                print(f"\n  缓存键值对:")
                for _, row in df.iterrows():
                    print(f"   {row['key']:15} | {row['value']:>12} | 更新: {row['updated_at']}")
                print(f"\n  📊 共 {len(df)} 条缓存数据")
            continue
        
        elif table_name == 'stock_meta':
            # 股票元数据缓存表
            df = pd.read_sql_query("SELECT * FROM stock_meta ORDER BY symbol", conn)
            print_header("💾 股票元数据缓存 - stock_meta")
            if df.empty:
                print("  📭 数据为空")
            else:
                print(f"\n  股票赛道/币种信息:")
                print(f"   {'代码':12} | {'赛道':20} | {'币种':8} | 更新时间")
                print(f"   {'-'*12} | {'-'*20} | {'-'*8} | {'-'*20}")
                for _, row in df.iterrows():
                    sector = row['sector'] or '-'
                    print(f"   {row['symbol']:12} | {sector:20} | {row['currency']:8} | {row['updated_at']}")
                print(f"\n  📊 共 {len(df)} 条元数据")
            continue
        
        elif table_name == 'stock_prices':
            # 股价缓存表 - 单独处理，关联持仓信息
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
                ORDER BY sp.updated_at DESC
            """, conn)
            print_header("💾 股价缓存 - stock_prices")
            if df.empty:
                print("  📭 数据为空")
            else:
                print(f"\n  代码         |     现价     |  来源   |      数量      |    更新时间")
                print(f"  {'-'*65}")
                for _, row in df.iterrows():
                    price = f"${row['current_price']:,.2f}" if row['current_price'] else "N/A"
                    qty = f"{row['quantity']:.2f}" if row['quantity'] else "-"
                    source = row['price_source'] or '-'
                    print(f"  {row['symbol']:13} | {price:>12} | {source:^7} | {qty:>13} | {row['updated_at']}")
                print(f"\n  📊 共 {len(df)} 条股价数据")
            continue
        
        elif table_name == 'sqlite_sequence':
            # 自增序列表，跳过
            continue
        
        # 获取表数据
        try:
            df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
            
            if df.empty:
                print_header(f"{table_name} (0 条)")
                print("  📭 表为空")
                continue
            
            # 针对不同表使用不同的展示格式
            if table_name == 'transactions':
                # 交易记录 - 格式化金额
                df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
                print_table_data(df, f"📈 交易记录 - {table_name}")
                
            elif table_name == 'fund_flows':
                # 资金流水 - 格式化金额
                df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
                df['amount'] = df['amount'].apply(lambda x: f"${x:,.2f}" if x > 0 else f"-${abs(x):,.2f}")
                print_table_data(df, f"💰 资金流水 - {table_name}")
                
            elif table_name == 'daily_snapshots':
                # 每日快照 - 格式化金额
                df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
                df['total_asset'] = df['total_asset'].apply(lambda x: f"${x:,.2f}" if pd.notna(x) else "N/A")
                df['total_invested'] = df['total_invested'].apply(lambda x: f"${x:,.2f}" if pd.notna(x) else "N/A")
                df['total_pnl'] = df['total_pnl'].apply(lambda x: f"${x:,.2f}" if pd.notna(x) else "N/A")
                print_table_data(df, f"📊 每日快照 - {table_name}")
                
            elif table_name == 'cash_balance':
                # 现金余额 - 简洁展示
                print_header(f"💵 现金余额 - {table_name}")
                balance = df['balance'].iloc[0] if 'balance' in df.columns else 'N/A'
                print(f"\n  当前余额: ${balance:,.2f}\n")
                
            else:
                # 其他表 - 通用展示
                print_table_data(df, f"📄 {table_name}")
                
        except Exception as e:
            print_header(f"❌ 读取 {table_name} 失败")
            print(f"  错误: {e}")
    
    conn.close()
    print("\n" + "=" * 60)
    print("  查询完成")
    print("=" * 60 + "\n")


def view_quick_summary():
    """快速概览"""
    if not os.path.exists(DB_PATH):
        print(f"❌ 数据库不存在: {DB_PATH}")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("\n" + "=" * 50)
    print("  📊 IM 投资数据库 - 快速概览")
    print("=" * 50)
    
    # 统计各表数据量
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = cursor.fetchall()
    
    summary = {}
    for table in tables:
        name = table[0]
        cursor.execute(f"SELECT COUNT(*) FROM {name}")
        count = cursor.fetchone()[0]
        summary[name] = count
    
    # 现金余额
    try:
        cursor.execute("SELECT balance FROM cash_balance WHERE id=1")
        balance = cursor.fetchone()[0]
        print(f"\n💵 现金余额: ${balance:,.2f}")
    except:
        print(f"\n💵 现金余额: N/A")
    
    # 总投入
    try:
        cursor.execute("""
            SELECT SUM(
                CASE 
                    WHEN type IN ('DEPOSIT', 'RESET') THEN amount 
                    WHEN type = 'WITHDRAW' THEN -amount 
                    ELSE 0 
                END
            ) FROM fund_flows
        """)
        invested = cursor.fetchone()[0] or 0
        print(f"📈 总投入: ${invested:,.2f}")
    except:
        print(f"📈 总投入: N/A")
    
    # 交易次数
    try:
        cursor.execute("SELECT COUNT(*) FROM transactions WHERE is_deleted=0")
        trades = cursor.fetchone()[0]
        print(f"📝 交易次数: {trades}")
    except:
        print(f"📝 交易次数: N/A")
    
    # 持仓股票数
    try:
        cursor.execute("SELECT COUNT(DISTINCT symbol) FROM transactions WHERE is_deleted=0")
        symbols = cursor.fetchone()[0]
        print(f"📦 持仓股票数: {symbols}")
    except:
        print(f"📦 持仓股票数: N/A")
    
    print("\n📋 数据表统计:")
    for name, count in summary.items():
        emoji = "💾" if name in ['macro_cache', 'stock_meta', 'stock_prices'] else "📄"
        print(f"   {emoji} {name}: {count} 条")
    
    conn.close()
    print("\n" + "=" * 50 + "\n")


if __name__ == "__main__":
    import pandas as pd
    
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == '--quick':
        view_quick_summary()
    else:
        view_all_data()
