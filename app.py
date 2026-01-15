import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import yfinance as yf
from datetime import date, datetime
import data_manager as db

# ================= 1. 页面配置与 CSS =================
st.set_page_config(page_title="长期主义资产管理", layout="wide", page_icon="🔭")
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

    /* 侧边栏隐藏 */
    section[data-testid="stSidebar"] { display: none; }

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

    /* 宏观指标微调 */
    div[data-testid="column"]:nth-child(1) div[data-testid="stMetric"] label {
        font-size: 14px;
        color: #666;
    }

    /* 净资产大卡片特殊样式 */
    div.net-asset-card div[data-testid="stMetric"] {
        background: linear-gradient(to right bottom, #ffffff, #f0fdf4);
        border-left: 5px solid #16a34a; 
    }

    /* 悬浮按钮样式 */
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


# ================= 2. 核心逻辑工具函数 =================

@st.cache_data(ttl=3600)
def get_exchange_rates():
    """获取基础汇率 (相对于 USD)"""
    return {'USD': 1.0, 'HKD': 0.128, 'CNY': 0.138, 'CNH': 0.138}


def detect_currency(symbol):
    """根据代码判断币种"""
    symbol = symbol.lower().strip()
    if symbol.isdigit() and len(symbol) == 5: return 'HKD'
    if symbol.startswith('hk'): return 'HKD'
    if symbol.startswith('sh') or symbol.startswith('sz') or (symbol.isdigit() and len(symbol) == 6): return 'CNY'
    return 'USD'


def get_realtime_price(symbol):
    """获取股票实时价格"""
    symbol = symbol.lower().strip()
    headers = {'Referer': 'https://finance.sina.com.cn'}
    try:
        if ' ' in symbol: return None
        if symbol.isalpha():  # 美股
            url = f"https://hq.sinajs.cn/list=gb_{symbol}"
            resp = requests.get(url, headers=headers, timeout=2)
            content = resp.text.split('="')[1].split(',')
            if len(content) > 1: return float(content[1])
        else:  # A股/港股
            if not (symbol.startswith('sh') or symbol.startswith('sz') or symbol.startswith('hk')):
                if len(symbol) == 5:
                    prefix = 'hk'
                else:
                    prefix = 'sh' if symbol.startswith('6') else 'sz'
                symbol = prefix + symbol
            url = f"https://hq.sinajs.cn/list={symbol}"
            resp = requests.get(url, headers=headers, timeout=2)
            content = resp.text.split('="')[1].split(',')
            if len(content) > 3: return float(content[6] if 'hk' in symbol else content[3])
    except:
        return None
    return None


@st.cache_data(ttl=1800)
def get_macro_data():
    """获取宏观指标 (Yahoo Finance)"""
    vix, tnx = None, None
    try:
        try:
            vix_ticker = yf.Ticker("^VIX")
            hist = vix_ticker.history(period="1d")
            if not hist.empty: vix = hist['Close'].iloc[-1]
        except:
            pass

        try:
            tnx_ticker = yf.Ticker("^TNX")
            hist = tnx_ticker.history(period="1d")
            if not hist.empty: tnx = hist['Close'].iloc[-1]
        except:
            pass

        return vix, tnx
    except:
        return None, None


@st.cache_data(ttl=86400)
def get_stock_sector(symbol):
    """获取股票行业标签 (自动汉化)"""
    symbol = symbol.lower().strip()
    yf_symbol = symbol
    if symbol.isdigit() and len(symbol) == 5:
        yf_symbol = f"{symbol}.HK"
    elif symbol.startswith('hk'):
        yf_symbol = f"{symbol[2:]}.HK"
    elif symbol.startswith('sh'):
        yf_symbol = f"{symbol[2:]}.SS"
    elif symbol.startswith('sz'):
        yf_symbol = f"{symbol[2:]}.SZ"

    sector_map = {
        'Technology': '💻 科技', 'Financial Services': '🏦 金融', 'Consumer Cyclical': '🛍️ 消费(周期)',
        'Consumer Defensive': '🛡️ 消费(防御)', 'Healthcare': '💊 医药', 'Communication Services': '📡 通信',
        'Energy': '🛢️ 能源', 'Industrials': '🏭 工业', 'Real Estate': '🏠 地产', 'Basic Materials': '🧱 原材料',
        'Utilities': '⚡ 公用事业'
    }
    try:
        ticker = yf.Ticker(yf_symbol)
        sec = ticker.info.get('sector', 'Unknown')
        return sector_map.get(sec, sec)
    except:
        return "N/A"


def calculate_option_intrinsic_value(option_row, underlying_price):
    """期权内在价值"""
    if underlying_price <= 0: return 0
    strike = option_row.get('strike')
    o_type = option_row.get('option_type')
    if not strike or not o_type: return 0

    if o_type == 'CALL':
        return max(0, underlying_price - strike)
    elif o_type == 'PUT':
        return max(0, strike - underlying_price)
    return 0


def update_portfolio_valuation(df):
    """统一汇率 + 期权估值 + 行业标签 + 币种标记"""
    rates = get_exchange_rates()
    current_prices = []
    mkt_values_usd = []
    sectors = []
    currencies = []

    for i, row in df.iterrows():
        raw_sym = row['Raw Symbol']
        currency = detect_currency(raw_sym)
        currencies.append(currency)
        rate = rates.get(currency, 1.0)

        price = get_realtime_price(raw_sym)

        # 行业
        sec = get_stock_sector(raw_sym) if row['Type'] == 'STOCK' else "📜 期权"
        sectors.append(sec)

        # 估值
        final_price_native = 0
        if row['Type'] == 'STOCK':
            final_price_native = price if price else (row['Avg Cost'] or 0)
        elif row['Type'] == 'OPTION':
            final_price_native = calculate_option_intrinsic_value(row, price) if price else (row['Avg Cost'] or 0)

        val_usd = final_price_native * row['Quantity'] * row['Multiplier'] * rate
        current_prices.append(final_price_native)
        mkt_values_usd.append(val_usd)

    df['Price'] = current_prices
    df['Market Value'] = mkt_values_usd
    df['Sector'] = sectors
    df['Currency'] = currencies
    return df


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


# ================= 5. 主页面逻辑 =================

st.subheader("🔭 长期主义驾驶舱")

# --- 1. 宏观模块 ---
vix, tnx = get_macro_data()
mc1, mc2 = st.columns(2)

vix_val_str = f"{vix:.2f}" if vix else "N/A"
vix_label = "市场情绪"
vix_delta = "off"
if vix:
    if vix < 15:
        vix_delta = "inverse"
        vix_label = "市场过热 (贪婪)"
    elif vix > 30:
        vix_delta = "normal"
        vix_label = "黄金坑 (恐慌)"
    else:
        vix_label = "情绪平稳"

mc1.metric("🌊 VIX 恐慌指数", vix_val_str, vix_label, delta_color=vix_delta, help="<15: 贪婪(风险); >30: 恐慌(机会)。")
tnx_val_str = f"{tnx:.2f}%" if tnx else "N/A"
mc2.metric("⚓ 10年美债收益率", tnx_val_str, "资产定价重力", delta_color="off", help="无风险利率，资产估值的锚。")

st.markdown("---")

# --- 2. 个人资产计算 ---
portfolio_df = db.get_portfolio_summary()
total_invested = db.get_total_invested()
cash_balance = db.get_cash_balance()

market_val_usd = 0
total_cost_usd = 0

if not portfolio_df.empty:
    if 'last_update' not in st.session_state:
        portfolio_df = update_portfolio_valuation(portfolio_df)
        st.session_state['portfolio_cache'] = portfolio_df
        st.session_state['last_update'] = datetime.now()
    else:
        portfolio_df = st.session_state['portfolio_cache']

    market_val_usd = portfolio_df['Market Value'].sum()
    total_cost_usd = portfolio_df['Total Cost'].sum()

# --- 3. 净资产计算 ---
final_net_asset = market_val_usd + cash_balance

base = total_invested if total_invested > 0 else (total_cost_usd if total_cost_usd > 0 else 1)
pnl = final_net_asset - base
ret_pct = (pnl / base) * 100

db.save_daily_snapshot(date.today().strftime('%Y-%m-%d'), final_net_asset, base)

# 风控指标
lev_ratio = (market_val_usd / final_net_asset) if final_net_asset > 0 else 999
cash_ratio = (cash_balance / final_net_asset * 100) if final_net_asset > 0 else 0

top3_conc = 0
if market_val_usd > 0:
    top3_conc = (portfolio_df.nlargest(3, 'Market Value')['Market Value'].sum() / market_val_usd) * 100

# --- 4. 看板渲染 ---
with st.container():
    st.markdown('<div class="net-asset-card">', unsafe_allow_html=True)
    c_main = st.columns(1)[0]
    c_main.metric("💎 净资产 (Net Assets USD)", f"${final_net_asset:,.0f}", f"{ret_pct:+.2f}%")
    st.markdown('</div>', unsafe_allow_html=True)

st.write("")
c1, c2, c3, c4 = st.columns(4)
# === 修复点：这里使用了 lev_ratio，与上方定义一致 ===
c1.metric("⚖️ 杠杆率", f"{lev_ratio:.2f}x", delta="安全" if lev_ratio <= 1.2 else "偏高",
          delta_color="inverse" if lev_ratio > 1.2 else "normal")
c2.metric("🎯 Top3 集中度", f"{top3_conc:.1f}%")
c3.metric("🔫 现金/负债", f"${abs(cash_balance):,.0f}", f"{cash_ratio:+.1f}%")
c4.metric("🛡️ 利润安全垫", f"${pnl:,.0f}")

st.divider()

# --- 5. 多维透视图表与列表 ---
if not portfolio_df.empty or abs(cash_balance) > 1:
    col_l, col_r = st.columns([1, 1.8])

    with col_l:
        st.caption("资产分布透视")
        chart_tab1, chart_tab2, chart_tab3 = st.tabs(["持仓", "赛道", "币种"])

        pie_data = portfolio_df.copy()
        if cash_balance > 0:
            new_row = {'Symbol': 'CASH', 'Market Value': cash_balance, 'Sector': '💵 现金', 'Currency': 'USD'}
            pie_data = pd.concat([pie_data, pd.DataFrame([new_row])], ignore_index=True)

        valid_pie = pie_data[pie_data['Market Value'] > 0]

        with chart_tab1:
            if not valid_pie.empty:
                fig = px.pie(valid_pie, values='Market Value', names='Symbol', hole=0.5)
                fig.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=250, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("无数据")

        with chart_tab2:
            if not valid_pie.empty:
                sec_df = valid_pie.groupby('Sector')['Market Value'].sum().reset_index()
                fig = px.pie(sec_df, values='Market Value', names='Sector', hole=0.5)
                fig.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=250)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("无数据")

        with chart_tab3:
            if not valid_pie.empty:
                curr_df = valid_pie.groupby('Currency')['Market Value'].sum().reset_index()
                fig = px.pie(curr_df, values='Market Value', names='Currency', hole=0.5,
                             color_discrete_sequence=px.colors.qualitative.Pastel)
                fig.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=250)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("无数据")

    with col_r:
        st.caption("持仓明细 (自动折算 USD)")
        portfolio_df['PnL $'] = portfolio_df['Market Value'] - portfolio_df['Total Cost']
        portfolio_df['Safety Margin'] = portfolio_df.apply(
            lambda x: max(0, (x['Price'] - x['Avg Cost']) / x['Price'] * 100) if x['Price'] > 0 and x[
                'Type'] == 'STOCK' else 0, axis=1
        )

        display_df = portfolio_df.sort_values('Market Value', ascending=False)

        st.dataframe(
            display_df,
            column_order=["Sector", "Symbol", "Quantity", "Avg Cost", "Price", "Market Value", "Safety Margin",
                          "Days Held"],
            column_config={
                "Sector": st.column_config.TextColumn("赛道", width="small"),
                "Symbol": st.column_config.TextColumn("代码", width="small"),
                "Quantity": st.column_config.NumberColumn("持仓", format="%.0f"),
                "Avg Cost": st.column_config.NumberColumn("成本", format="%.2f"),
                "Price": st.column_config.NumberColumn("现价/内在", format="%.2f"),
                "Market Value": st.column_config.NumberColumn("美元市值", format="$%.0f"),
                "Safety Margin": st.column_config.ProgressColumn("安全边际", format="%.1f%%", min_value=0,
                                                                 max_value=100),
                "Days Held": st.column_config.NumberColumn("持有", format="%d天")
            },
            use_container_width=True, height=400, hide_index=True
        )

# 流水
st.subheader("📋 交易流水")
at = db.get_all_transactions(False)
if not at.empty:
    edited = st.data_editor(at[['id', 'date', 'symbol', 'type', 'quantity', 'price', 'note']], hide_index=True,
                            use_container_width=True, key="trans_editor")
    if st.session_state.get("trans_editor", {}).get("deleted_rows"):
        for idx in st.session_state["trans_editor"]["deleted_rows"]:
            db.soft_delete_transaction(int(at.iloc[idx]['id']))
        st.rerun()

# 悬浮按钮
st.markdown('<span id="fab-anchor"></span>', unsafe_allow_html=True)
if st.button("➕", key="fab_main"): show_add_modal()