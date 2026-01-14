import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from datetime import date, datetime
import data_manager as db

# ================= 1. 页面配置与 CSS =================
st.set_page_config(page_title="我的投资管理 Pro", layout="wide", page_icon="💰")
db.init_db()

st.markdown("""
<style>
    /* 全局样式 */
    html, body, [class*="css"] { font-family: 'Check', sans-serif; }
    th, td { text-align: center !important; }
    .stDataFrame { text-align: center !important; }
    div[data-testid="stDataEditor"] div[role="grid"] { text-align: center !important; }

    /* 隐藏顶部默认菜单 */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* 仪表盘卡片渲染 */
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        padding: 15px 20px;
        border-radius: 12px;
        border: 1px solid #e5e7eb;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
        transition: all 0.3s ease;
    }
    div[data-testid="stMetric"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 16px rgba(0,0,0,0.08);
        border-color: #d1d5db;
    }
    div[data-testid="column"]:first-child div[data-testid="stMetric"] {
        background: linear-gradient(to right bottom, #ffffff, #f8fafc);
        border-left: 5px solid #2563eb;
    }
</style>
""", unsafe_allow_html=True)


# ================= 2. 工具函数 =================
def get_realtime_price(symbol):
    symbol = symbol.lower().strip()
    headers = {'Referer': 'https://finance.sina.com.cn'}
    try:
        if ' ' in symbol: return None
        if symbol.isalpha():  # 美股
            url = f"https://hq.sinajs.cn/list=gb_{symbol}"
            resp = requests.get(url, headers=headers, timeout=2)
            content = resp.text.split('="')[1].split(',')
            if len(content) > 1: return float(content[1])
        else:  # A股
            if not (symbol.startswith('sh') or symbol.startswith('sz')):
                prefix = 'sh' if symbol.startswith('6') else 'sz'
                symbol = prefix + symbol
            url = f"https://hq.sinajs.cn/list={symbol}"
            resp = requests.get(url, headers=headers, timeout=2)
            content = resp.text.split('="')[1].split(',')
            if len(content) > 3: return float(content[3])
    except:
        return None
    return None


def update_and_save_snapshot():
    pass


# ================= 3. 弹窗逻辑 =================
@st.dialog("📝 操作中心")
def show_add_modal():
    tab1, tab2, tab3, tab4 = st.tabs(["股票交易", "期权交易", "资金进出", "♻️ 回收站"])

    # Tab 1: 股票
    with tab1:
        with st.form("add_stock_form"):
            c1, c2 = st.columns(2)
            t_date = c1.date_input("日期", date.today())
            t_sym = c2.text_input("代码", "NVDA").upper()
            c3, c4 = st.columns(2)
            t_type = c3.selectbox("方向", ["BUY", "SELL"])
            t_qty = c4.number_input("数量 (股)", 0.0, step=100.0)
            c5, c6 = st.columns(2)
            t_price = c5.number_input("单价", 0.0, step=0.1)
            t_fee = c6.number_input("佣金", 0.0)
            t_note = st.text_input("笔记", placeholder="策略备注")
            if st.form_submit_button("提交股票交易", use_container_width=True):
                db.add_transaction(t_date, t_sym, t_type, t_qty, t_price, t_fee, t_note, asset_category='STOCK',
                                   multiplier=1)
                st.success("已保存")
                st.rerun()

    # Tab 2: 期权
    with tab2:
        with st.form("add_option_form"):
            c1, c2 = st.columns(2)
            o_date = c1.date_input("交易日期", date.today())
            o_sym = c2.text_input("正股代码", "NVDA").upper()
            c3, c4, c5 = st.columns(3)
            o_exp = c3.date_input("到期日")
            o_strike = c4.number_input("行权价", 0.0, step=5.0)
            o_type = c5.selectbox("类型", ["CALL", "PUT"])
            c6, c7 = st.columns(2)
            o_side = c6.selectbox("方向", ["BUY", "SELL"])
            o_qty = c7.number_input("张数", 1.0, step=1.0)
            c8, c9 = st.columns(2)
            o_price = c8.number_input("权利金", 0.0, step=0.1)
            o_fee = c9.number_input("佣金", 0.0)
            if st.form_submit_button("提交期权交易", use_container_width=True):
                db.add_transaction(o_date, o_sym, o_side, o_qty, o_price, o_fee, f"Option {o_type} {o_strike}",
                                   asset_category='OPTION', multiplier=100, strike=o_strike, expiration=str(o_exp),
                                   option_type=o_type)
                st.success("期权交易已保存")
                st.rerun()

    # Tab 3: 资金
    with tab3:
        mode = st.selectbox("模式", ["资金流水", "余额校准"], label_visibility="collapsed", key="fund_mode_sel")
        if mode == "资金流水":
            with st.form("fund_form"):
                f_date = st.date_input("日期", date.today())
                c1, c2 = st.columns(2)
                f_type = c1.selectbox("类型", ["DEPOSIT", "WITHDRAW"])
                f_amount = c2.number_input("金额", 1000.0, step=100.0)
                f_note = st.text_input("备注")
                if st.form_submit_button("提交", use_container_width=True):
                    db.add_fund_flow(f_date, f_type, f_amount, f_note)
                    st.success("已记录")
                    st.rerun()
        else:
            curr = db.get_cash_balance()
            with st.form("fix_balance_form"):
                st.markdown(f"当前余额: **${curr:,.2f}**")
                target = st.number_input("实际余额", value=float(curr))
                if st.form_submit_button("校准", use_container_width=True):
                    db.set_cash_balance(target, date.today())
                    st.success("已校准")
                    st.rerun()
        st.divider()
        funds = db.get_fund_flows(include_calib=False)
        if not funds.empty:
            funds = funds.reset_index(drop=True)
            display_f = funds.copy()
            display_f['display_type'] = display_f['type'].map({'DEPOSIT': '入金', 'WITHDRAW': '出金'})
            edited = st.data_editor(display_f, column_config={"id": None, "type": None, "display_type": "类型"},
                                    hide_index=True, key="fund_list_editor")
            if st.session_state.get("fund_list_editor", {}).get("deleted_rows"):
                for idx in st.session_state["fund_list_editor"]["deleted_rows"]:
                    db.delete_fund_flow(funds.iloc[idx]['id'])
                st.rerun()

    # Tab 4: 回收站
    with tab4:
        deleted = db.get_deleted_transactions_last_7_days()
        if not deleted.empty:
            for idx, row in deleted.iterrows():
                c1, c2 = st.columns([4, 1])
                c1.text(f"{row['symbol']} {row['type']} {row['quantity']}")
                if c2.button("恢复", key=f"res_{row['id']}"):
                    db.restore_transaction(row['id'])
                    st.rerun()
        else:
            st.caption("空")


# ================= 5. 主页面: 长期主义看板 =================
st.subheader("🔭 长期布局看板")

# 1. 获取数据
portfolio_df = db.get_portfolio_summary()
total_invested_funds = db.get_total_invested()
cash_balance = db.get_cash_balance()

# 2. 计算市值
market_value_total = 0
total_holdings_cost = 0

if not portfolio_df.empty:
    if 'last_update' not in st.session_state:
        p_bar = st.progress(0, text="同步行情...")
        current_prices = []
        mkt_values = []

        for i, row in portfolio_df.iterrows():
            if row['Type'] == 'STOCK':
                price = get_realtime_price(row['Raw Symbol'])
                if price is None: price = row['Avg Cost'] or 0
            else:
                price = row['Avg Cost'] or 0

            current_prices.append(price)
            val = price * row['Quantity'] * row['Multiplier']
            mkt_values.append(val)
            p_bar.progress((i + 1) / len(portfolio_df))
        p_bar.empty()

        portfolio_df['Price'] = current_prices
        portfolio_df['Market Value'] = mkt_values
        st.session_state['portfolio_cache'] = portfolio_df
        st.session_state['last_update'] = datetime.now()
    else:
        portfolio_df = st.session_state['portfolio_cache']

    market_value_total = portfolio_df['Market Value'].sum()
    total_holdings_cost = portfolio_df['Total Cost'].sum()

# 3. 计算核心指标
final_total_asset = market_value_total + cash_balance

if total_invested_funds > 0:
    final_invested = total_invested_funds
    total_pnl = final_total_asset - final_invested
else:
    final_invested = total_holdings_cost if total_holdings_cost > 0 else 1
    total_pnl = market_value_total - total_holdings_cost

ret_rate = (total_pnl / final_invested * 100)
db.save_daily_snapshot(date.today().strftime('%Y-%m-%d'), final_total_asset, final_invested)

# 4. 计算风控指标
if final_total_asset > 0:
    leverage_ratio = market_value_total / final_total_asset
else:
    leverage_ratio = 999.0

top3_concentration = 0
if market_value_total > 0:
    top3_val = portfolio_df.nlargest(3, 'Market Value')['Market Value'].sum()
    top3_concentration = (top3_val / market_value_total) * 100

cash_weight = (cash_balance / final_total_asset * 100) if final_total_asset > 0 else 0

# ================= 渲染看板 (UI) =================

c_main = st.columns(1)[0]
c_main.metric("💎 净资产 (Net Assets)", f"${final_total_asset:,.0f}", f"{ret_rate:+.2f}% (总收益率)")

st.write("")

c1, c2, c3, c4 = st.columns(4)
c1.metric("⚖️ 杠杆率", f"{leverage_ratio:.2f}x", delta="安全" if leverage_ratio <= 1.2 else "偏高",
          delta_color="normal" if leverage_ratio <= 1.2 else "inverse", help="持仓市值 / 净资产")
c2.metric("🎯 Top3 集中度", f"{top3_concentration:.1f}%", help="前三大持仓占比")
c3.metric("🔫 干火药/负债", f"${abs(cash_balance):,.0f}", f"{cash_weight:+.1f}% (仓位)",
          delta_color="normal" if cash_balance >= 0 else "inverse")
c4.metric("🛡️ 利润安全垫", f"${total_pnl:,.0f}", help="累计总盈利")

st.divider()

# ================= 图表与列表 =================
if not portfolio_df.empty or abs(cash_balance) > 1:
    col_chart1, col_chart2 = st.columns([1, 1.8])  # 表格更宽一点

    with col_chart1:
        st.caption("资产分布 (Long Only)")
        pie_data = portfolio_df[['Symbol', 'Market Value']].copy()
        if cash_balance > 0:
            pie_data.loc[len(pie_data)] = {'Symbol': 'CASH 💵', 'Market Value': cash_balance}

        valid_pie = pie_data[pie_data['Market Value'] > 0]
        if not valid_pie.empty:
            fig = px.pie(valid_pie, values='Market Value', names='Symbol', hole=0.5)
            fig.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=280)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("无正资产")

        if not valid_pie.empty:  # 负债提示
            liabilities = pie_data[pie_data['Market Value'] < 0]
            if not liabilities.empty:
                st.warning(f"📉 包含负债: ${liabilities['Market Value'].sum():,.0f}")

    with col_chart2:
        st.caption("持仓明细 (含长线指标)")

        # 1. 计算扩展指标
        portfolio_df['PnL $'] = portfolio_df['Market Value'] - portfolio_df['Total Cost']
        portfolio_df['PnL %'] = (portfolio_df['PnL $'] / portfolio_df['Total Cost'].replace(0, 1) * 100).fillna(0)

        # 2. 安全边际 (修复版：*100)
        portfolio_df['Safety Margin'] = portfolio_df.apply(
            lambda x: max(0, (x['Price'] - x['Avg Cost']) / x['Price'] * 100) if x['Price'] > 0 else 0, axis=1
        )

        # 3. 排序 (按市值降序)
        display_df = portfolio_df.sort_values('Market Value', ascending=False)

        # 4. 渲染高级表格
        st.dataframe(
            display_df,
            column_order=["Symbol", "Quantity", "Avg Cost", "Price", "Market Value", "PnL $", "PnL %", "Safety Margin",
                          "Days Held"],
            column_config={
                "Symbol": st.column_config.TextColumn("代码", width="small"),
                "Quantity": st.column_config.NumberColumn("持仓", format="%.0f"),
                "Avg Cost": st.column_config.NumberColumn("成本", format="%.2f"),
                "Price": st.column_config.NumberColumn("现价", format="%.2f"),
                "Market Value": st.column_config.NumberColumn("市值", format="$%.0f"),
                "PnL $": st.column_config.NumberColumn("盈亏额", format="$%+.0f"),
                "PnL %": st.column_config.NumberColumn("盈亏率", format="%+.2f%%"),

                # 🔥 进度条 0-100
                "Safety Margin": st.column_config.ProgressColumn(
                    "安全边际",
                    help="现价距离成本价的跌幅缓冲空间 (越长越安全)",
                    format="%.1f%%",
                    min_value=0,
                    max_value=100,
                ),

                "Days Held": st.column_config.NumberColumn(
                    "持有天数",
                    help="从第一次买入至今的天数",
                    format="%d 天"
                )
            },
            use_container_width=True,
            height=400,
            hide_index=True
        )
else:
    st.info("暂无持仓")

# ================= 交易流水 =================
st.subheader("📋 交易流水")
all_trans = db.get_all_transactions(include_deleted=False)
if not all_trans.empty:
    cols = ['id', 'date', 'symbol', 'type', 'quantity', 'price', 'fee', 'note']
    if 'note' not in all_trans.columns: all_trans['note'] = ""

    edited_df = st.data_editor(
        all_trans[cols],
        column_config={"id": None, "quantity": st.column_config.NumberColumn(format="%.0f"),
                       "price": st.column_config.NumberColumn(format="%.2f")},
        hide_index=True, use_container_width=True, num_rows="dynamic", key="trans_editor"
    )
    if st.session_state.get("trans_editor", {}).get("deleted_rows"):
        for idx in st.session_state["trans_editor"]["deleted_rows"]:
            db.soft_delete_transaction(int(all_trans.iloc[idx]['id']))
        st.rerun()

# ================= 悬浮按钮 =================
st.markdown('<span id="fab-anchor"></span>', unsafe_allow_html=True)
if st.button("➕", key="fab_main"):
    show_add_modal()

st.markdown("""
<style>
    div.stButton:has(button:active), div.stButton:last-of-type {
        position: fixed; bottom: 40px; right: 40px; z-index: 9999; width: auto;
    }
    div.stButton:last-of-type > button {
        border-radius: 50%; width: 60px; height: 60px; font-size: 24px;
        background-color: #FF4B4B; color: white; box-shadow: 0px 4px 10px rgba(0,0,0,0.3); border: none;
    }
    div[data-testid="stDialog"] div.stButton { position: static !important; width: auto !important; }
    div[data-testid="stDialog"] button { border-radius: 4px !important; width: auto !important; height: auto !important; font-size: 1rem !important; box-shadow: none !important; }
</style>
""", unsafe_allow_html=True)