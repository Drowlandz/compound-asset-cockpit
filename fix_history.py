import sqlite3
import pandas as pd
import os

# 数据库文件路径
DB_NAME = "investments.db"


def fix_data():
    if not os.path.exists(DB_NAME):
        print(f"❌ 错误：找不到数据库文件 {DB_NAME}")
        return

    print(f"🔌 连接数据库: {DB_NAME}...")
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # 1. 检查 daily_snapshots 表是否有 total_invested 列
    # 如果是旧版数据库，可能连列都没有，先补上
    try:
        c.execute("SELECT total_invested FROM daily_snapshots LIMIT 1")
    except sqlite3.OperationalError:
        print("⚠️ 检测到旧版表结构，正在添加 total_invested 列...")
        c.execute("ALTER TABLE daily_snapshots ADD COLUMN total_invested REAL DEFAULT 0")
        conn.commit()

    # 2. 读取所有历史快照 (资产数据)
    df_snaps = pd.read_sql_query("SELECT date, total_asset FROM daily_snapshots ORDER BY date", conn)

    if df_snaps.empty:
        print("⚠️ 警告：daily_snapshots 表是空的，没有历史资产数据可以修复。")
        conn.close()
        return

    # 3. 读取所有资金流水 (本金数据)
    df_flows = pd.read_sql_query("SELECT date, type, amount FROM fund_flows ORDER BY date", conn)

    print(f"📊 发现 {len(df_snaps)} 条历史资产记录，开始回溯计算本金...")

    update_count = 0

    # 4. 核心逻辑：逐日回溯
    for index, row in df_snaps.iterrows():
        curr_date = row['date']

        # 筛选出 [截止到这一天] 的所有流水
        # 逻辑：总本金 = (入金 + 初始 + 重置) - 出金
        if not df_flows.empty:
            past_flows = df_flows[df_flows['date'] <= curr_date]

            # 计算累计入金 (DEPOSIT, INITIAL, RESET 都算正向投入)
            plus = past_flows[past_flows['type'].isin(['DEPOSIT', 'INITIAL', 'RESET'])]['amount'].sum()

            # 计算累计出金
            minus = past_flows[past_flows['type'] == 'WITHDRAW']['amount'].sum()

            # 得出当天的实际总本金
            historical_invested = plus - minus
        else:
            historical_invested = 0.0

        # 5. 将计算出的本金写回数据库
        c.execute("UPDATE daily_snapshots SET total_invested = ? WHERE date = ?", (historical_invested, curr_date))
        update_count += 1

        # 打印进度条效果
        if update_count % 10 == 0:
            print(f"   -> 已处理至 {curr_date}: 当时本金 ${historical_invested:,.0f}")

    conn.commit()
    conn.close()

    print("-" * 30)
    print(f"✅ 修复完成！共更新了 {update_count} 条历史记录。")
    print("🚀 现在请重新运行 app.py，收益率曲线应该已经出现了！")


if __name__ == "__main__":
    fix_data()