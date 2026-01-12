import streamlit as st
import plotly.express as px
from datetime import date
import data_manager as db
import requests

# 1. 页面配置
st.set_page_config(page_title="我的投资管理", layout="wide")
st.title("💰 个人投资仪表盘")

# 初始化数据库
db.init_db()

# ================= Sidebar: 交易录入 =================
with st.sidebar:
    st.header("📝 录入新交易")
    with st.form("add_trade_form"):
        trade_date = st.date_input("日期", date.today())
        symbol = st.text_input("代码 (如 NVDA, AAPL)", "NVDA")
        t_type = st.selectbox("类型", ["BUY", "SELL"])
        qty = st.number_input("数量", min_value=0.01, step=1.0)
        price = st.number_input("单价 ($)", min_value=0.01, step=0.1)
        fee = st.number_input("手续费 ($)", min_value=0.0, value=0.0)
        note = st.text_area("笔记 (可选)")

        submitted = st.form_submit_button("提交记录")
        if submitted:
            db.add_transaction(trade_date, symbol, t_type, qty, price, fee, note)
            st.success(f"已保存: {symbol} {t_type}")

# ================= Main: 数据概览 =================

def get_realtime_price(symbol):
    """
    从新浪财经获取实时价格 (支持美股和A股)
    """
    symbol = symbol.lower().strip()
    headers = {'Referer': 'https://finance.sina.com.cn'}

    try:
        # 1. 简单的逻辑判断：如果是纯字母，默认当做美股处理
        if symbol.isalpha():
            # 美股接口: hq.sinajs.cn/list=gb_nvda
            url = f"https://hq.sinajs.cn/list=gb_{symbol}"
            resp = requests.get(url, headers=headers)
            text = resp.text
            # 返回格式: var hq_str_gb_nvda="NVIDIA,135.20,..."
            content = text.split('="')[1].split(',')
            if len(content) > 1:
                return float(content[1])  # 美股现价在第1位

        # 2. 如果包含数字 (如 600519 或 sh600519)，当做A股处理
        else:
            # 自动补全后缀，新浪接口需要 sh/sz 前缀
            # 如果用户只输了 600519，默认尝试加 sh (并不严谨，作为示例)
            # 建议用户录入时带上 sh/sz，或者这里写更复杂的判断逻辑
            if not (symbol.startswith('sh') or symbol.startswith('sz')):
                # 简单粗暴修正：6开头是sh，0/3开头是sz
                if symbol.startswith('6'):
                    prefix = 'sh'
                else:
                    prefix = 'sz'
                symbol = prefix + symbol

            url = f"https://hq.sinajs.cn/list={symbol}"
            resp = requests.get(url, headers=headers)
            text = resp.text
            # 返回格式: var hq_str_sh600519="贵州茅台,27.55,27.25,26.91,..."
            content = text.split('="')[1].split(',')
            if len(content) > 3:
                return float(content[3])  # A股现价在第3位

    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
        return None

    return None


# 1. 获取持仓数据
portfolio_df = db.get_portfolio_summary()

if portfolio_df.empty:
    st.info("👋 还没有持仓，请在左侧录入第一笔交易！")
else:
    st.subheader("📊 持仓概览")

    # 进度条
    progress_bar = st.progress(0, text="正在通过新浪财经极速接口获取数据...")

    current_prices = []
    market_values = []
    pnl_values = []
    pnl_percents = []

    total_items = len(portfolio_df)

    for idx, row in portfolio_df.iterrows():
        sym = row['Symbol']

        # === 调用新接口 ===
        price = get_realtime_price(sym)

        if price is None:
            # 如果获取失败，暂时用成本价代替，避免报错，并提示
            price = row['Avg Cost']
            st.toast(f"⚠️ 无法获取 {sym} 的价格，已按成本计算。", icon="⚠️")

        # 更新进度条
        progress_bar.progress((idx + 1) / total_items)

        # 计算逻辑
        qty = row['Quantity']
        cost = row['Total Cost']

        mkt_val = price * qty
        pnl = mkt_val - cost
        pnl_pct = (pnl / cost) * 100 if cost != 0 else 0

        current_prices.append(price)
        market_values.append(mkt_val)
        pnl_values.append(pnl)
        pnl_percents.append(pnl_pct)

    progress_bar.empty()  # 完成后隐藏进度条

    # 将计算结果填回 DataFrame
    portfolio_df['Current Price'] = [round(p, 2) for p in current_prices]
    portfolio_df['Market Value'] = [round(v, 2) for v in market_values]
    portfolio_df['Unrealized PnL'] = [round(p, 2) for p in pnl_values]
    portfolio_df['Return %'] = [round(p, 2) for p in pnl_percents]

    # --- 下面的 UI 代码保持不变 (KPI卡片, 图表等) ---
    total_asset = portfolio_df['Market Value'].sum()
    total_cost = portfolio_df['Total Cost'].sum()
    total_pnl = total_asset - total_cost
    total_return_rate = (total_pnl / total_cost * 100) if total_cost != 0 else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("总资产", f"${total_asset:,.2f}")
    col2.metric("总投入", f"${total_cost:,.2f}")
    col3.metric("总浮盈", f"${total_pnl:,.2f}", delta_color="normal")
    col4.metric("总收益率", f"{total_return_rate:.2f}%", delta=f"{total_return_rate:.2f}%")

    st.divider()

    c1, c2 = st.columns([1, 1])
    with c1:
        st.caption("持仓占比 (按市值)")
        # 饼图
        fig_pie = px.pie(portfolio_df, values='Market Value', names='Symbol', hole=0.4)
        st.plotly_chart(fig_pie, use_container_width=True)

    with c2:
        st.caption("个股盈亏贡献 (金额)")
        # 柱状图
        fig_bar = px.bar(portfolio_df, x='Symbol', y='Unrealized PnL',
                         color='Unrealized PnL',
                         color_continuous_scale=['red', 'green'])  # 简单的红绿配色
        st.plotly_chart(fig_bar, use_container_width=True)

    st.dataframe(portfolio_df.style.format({
        "Avg Cost": "${:.2f}",
        "Current Price": "${:.2f}",
        "Market Value": "${:.2f}",
        "Return %": "{:.2f}%"
    }), use_container_width=True)

# ================= Bottom: 历史记录 =================
with st.expander("查看所有交易记录"):
    st.dataframe(db.get_all_transactions())