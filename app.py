import streamlit as st
import pandas as pd
import requests
import yfinance as yf
import random
from datetime import date, datetime
import data_manager as db
from streamlit_echarts import st_echarts

# ================= 1. 页面配置与 CSS (UI 重构版) =================
st.set_page_config(page_title="长期主义资产管理", layout="wide", page_icon="🔭")
db.init_db()

st.markdown("""
<style>
    /* === 全局基础 === */
    html, body, [class*="css"] { font-family: 'Check', -apple-system, system-ui, sans-serif; }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    section[data-testid="stSidebar"] { display: none; }

    /* === 1. 魔改切换按钮 (Segmented Control) === */
    /* 隐藏原本的圆圈单选框 */
    div[role="radiogroup"] label > div:first-child {
        display: none;
    }

    /* 容器样式 */
    div[role="radiogroup"] {
        background-color: #f1f5f9; /* 浅灰底色 */
        padding: 4px;
        border-radius: 12px;
        display: inline-flex;
        border: 1px solid #e2e8f0;
        gap: 0px; /* 紧凑布局 */
    }

    /* 选项按钮样式 */
    div[role="radiogroup"] label {
        border: none;
        padding: 8px 20px;
        border-radius: 8px;
        margin: 0;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        color: #64748b; /* 未选中文字颜色 */
        font-weight: 500;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
    }

    /* 选中状态 (Streamlit 会给选中的 label 加特定 class，这里我们利用层级覆盖) */
    /* 由于 CSS 无法直接选父级，我们用背景色技巧：
       默认状态下背景透明，选中的文字会变色。
       为了实现完美的 iOS 白色滑块效果，需要更复杂的 hack，
       这里使用"视觉欺骗"法：给选中的文字加粗变深色，鼠标悬浮有白底。
    */
    div[role="radiogroup"] label:hover {
        background-color: #ffffff;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        color: #0f172a;
    }

    /* 选中项的文字样式 (Streamlit 默认会处理 checked 的颜色，我们加强它) */
    div[role="radiogroup"] div[data-checked="true"] {
        background-color: #ffffff !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        border-radius: 8px;
        color: #0f172a !important;
        font-weight: bold;
        transform: scale(1.02);
    }

    /* === 2. 荣誉勋章 (右上角悬浮 + 呼吸灯) === */
    @keyframes breathe {
        0% { box-shadow: 0 0 5px rgba(255, 215, 0, 0.3); transform: scale(1); }
        50% { box-shadow: 0 0 15px rgba(255, 215, 0, 0.6); transform: scale(1.02); }
        100% { box-shadow: 0 0 5px rgba(255, 215, 0, 0.3); transform: scale(1); }
    }
    .badge-container {
        position: fixed; top: 60px; right: 30px; z-index: 9999;
        background: rgba(255, 255, 255, 0.95);
        backdrop-filter: blur(5px);
        border: 1px solid #eab308; /* 金色边框 */
        border-left: 6px solid #eab308;
        border-radius: 8px; 
        padding: 8px 16px;
        display: flex; align-items: center; gap: 12px;
        box-shadow: 0 10px 25px rgba(234, 179, 8, 0.15);
        animation: breathe 4s infinite ease-in-out;
        transition: transform 0.3s;
    }
    .badge-container:hover { transform: translateY(-2px); }
    .badge-icon { font-size: 28px; filter: drop-shadow(0 2px 2px rgba(0,0,0,0.1)); }
    .badge-text { font-family: 'Segoe UI', sans-serif; font-weight: 800; color: #854d0e; font-size: 15px; line-height: 1.1; }
    .badge-label { font-size: 11px; color: #a16207; font-weight: 500; margin-top: 2px; }

    /* === 3. 卡片与布局优化 === */
    /* 语录卡片 */
    .quote-card {
        background: linear-gradient(to right, #f8f9fa, #fff);
        border-left: 4px solid #3b82f6;
        padding: 12px 20px;
        margin-bottom: 25px;
        border-radius: 0 8px 8px 0;
        font-family: 'Georgia', serif;
        font-style: italic;
        color: #374151;
        font-size: 16px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.02);
    }
    .quote-author { text-align: right; font-weight: 600; font-size: 13px; color: #9ca3af; margin-top: 4px; font-style: normal; }

    /* 核心指标卡片 */
    div[data-testid="stMetric"] {
        background-color: #ffffff; padding: 18px 24px; border-radius: 16px;
        border: 1px solid #f1f5f9; 
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.01), 0 2px 4px -1px rgba(0, 0, 0, 0.01);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }
    div[data-testid="stMetric"]:hover {
        transform: translateY(-5px);
        box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.05), 0 10px 10px -5px rgba(0, 0, 0, 0.01);
        border-color: #cbd5e1;
    }
    div[data-testid="column"]:nth-child(1) div[data-testid="stMetric"] label { font-size: 13px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; color: #64748b; }

    /* 净资产卡片 (极光绿渐变) */
    div.net-asset-card div[data-testid="stMetric"] {
        background: linear-gradient(120deg, #ffffff 0%, #ecfdf5 100%);
        border: 1px solid #a7f3d0;
        border-left: 6px solid #059669;
    }

    /* 悬浮按钮 */
    div.stButton:has(button:active), div.stButton:last-of-type {
        position: fixed; bottom: 40px; right: 40px; z-index: 9999; width: auto;
    }
    div.stButton:last-of-type > button {
        border-radius: 50%; width: 64px; height: 64px; font-size: 28px;
        background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
        color: white; box-shadow: 0 10px 25px rgba(220, 38, 38, 0.4); 
        border: 2px solid #fff;
        transition: transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1);
    }
    div.stButton:last-of-type > button:hover { transform: scale(1.15) rotate(90deg); box-shadow: 0 15px 35px rgba(220, 38, 38, 0.5); }

    /* 修正弹窗按钮 */
    div[data-testid="stDialog"] div.stButton { position: static !important; width: auto !important; }
    div[data-testid="stDialog"] button { border-radius: 6px !important; width: auto !important; height: auto !important; font-size: 1rem !important; background: #f1f5f9; color: #0f172a; border: 1px solid #cbd5e1; box-shadow: none; }
    div[data-testid="stDialog"] button:hover { background: #e2e8f0; }
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
def get_global_macro_data():
    """获取全球宏观数据"""
    data = {'vix': None, 'tnx': None, 'vhsi': None, 'cnh': None}
    try:
        data['vix'] = yf.Ticker("^VIX").history(period="1d")['Close'].iloc[-1]
    except:
        pass
    try:
        data['tnx'] = yf.Ticker("^TNX").history(period="1d")['Close'].iloc[-1]
    except:
        pass
    try:
        data['vhsi'] = yf.Ticker("^VHSI").history(period="5d")['Close'].iloc[-1]
    except:
        pass
    try:
        data['cnh'] = yf.Ticker("CNH=X").history(period="5d")['Close'].iloc[-1]
    except:
        pass
    return data


@st.cache_data(ttl=86400)
def get_stock_sector(symbol):
    """获取股票行业标签"""
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
        sec = get_stock_sector(raw_sym) if row['Type'] == 'STOCK' else "📜 期权"
        sectors.append(sec)

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


# 🔥 ECharts 3D 饼图
def render_echarts_pie(df, name_col, value_col, title_text=""):
    data_list = [{"value": row[value_col], "name": row[name_col]} for _, row in df.iterrows()]
    options = {
        "tooltip": {"trigger": "item", "formatter": "{b}: ${c} ({d}%)"},
        "legend": {"show": False},
        "series": [{
            "name": title_text,
            "type": "pie",
            "radius": ["45%", "75%"],
            "itemStyle": {"borderRadius": 8, "borderColor": "#fff", "borderWidth": 2},
            "label": {"show": False},
            "emphasis": {
                "label": {"show": True, "fontSize": 18, "fontWeight": "bold", "formatter": "{b}\n{d}%",
                          "color": "#333"},
                "scale": True, "scaleSize": 15,
                "itemStyle": {"shadowBlur": 20, "shadowOffsetX": 0, "shadowColor": "rgba(0, 0, 0, 0.2)"}
            },
            "data": data_list
        }]
    }
    st_echarts(options=options, height="280px")


# 🔥 ECharts 历史净值面积图
def render_history_chart(history_df):
    if history_df.empty: return
    dates = pd.to_datetime(history_df['date']).dt.strftime('%Y-%m-%d').tolist()
    values = [float(x) for x in history_df['total_asset'].tolist()]

    options = {
        "tooltip": {"trigger": 'axis', "formatter": "📅 {b}<br/>💰 净资产: ${c}",
                    "backgroundColor": "rgba(255,255,255,0.9)", "textStyle": {"color": "#333"}},
        "grid": {"top": "15%", "left": "2%", "right": "4%", "bottom": "5%", "containLabel": True},
        "xAxis": {
            "type": 'category', "boundaryGap": False, "data": dates,
            "axisLine": {"show": False}, "axisTick": {"show": False}, "axisLabel": {"color": "#94a3b8"}
        },
        "yAxis": {"type": 'value', "splitLine": {"lineStyle": {"type": "dashed", "color": "#f1f5f9"}},
                  "axisLabel": {"formatter": "${value}", "color": "#94a3b8"}},
        "series": [{
            "name": '净资产', "type": 'line', "smooth": True, "lineStyle": {"width": 4, "color": "#16a34a"},
            "showSymbol": False,
            "areaStyle": {
                "opacity": 0.8,
                "color": {"type": 'linear', "x": 0, "y": 0, "x2": 0, "y2": 1,
                          "colorStops": [{"offset": 0, "color": 'rgba(22, 163, 74, 0.3)'},
                                         {"offset": 1, "color": 'rgba(22, 163, 74, 0.0)'}]}
            },
            "data": values
        }]
    }
    st_echarts(options=options, height="320px")


def get_badge_info(days):
    if days >= 1825: return "💎", "钻石手"
    if days >= 1095: return "🥇", "长期主义者"
    if days >= 365:  return "🥈", "时间的朋友"
    if days >= 90:   return "🥉", "坚守者"
    if days >= 30:   return "👀", "观察员"
    return "🌱", "新手"


# ================= 3. 弹窗逻辑 =================
@st.dialog("📝 操作中心")
def show_add_modal():
    tab1, tab2, tab3, tab4 = st.tabs(["股票交易", "期权交易", "资金进出", "♻️ 回收站"])

    # Tab 1: 股票
    with tab1:
        t_type = st.radio("交易方向", ["BUY (买入)", "SELL (卖出)"], horizontal=True)
        is_sell = "SELL" in t_type

        current_holdings = db.get_portfolio_summary()
        valid_holdings = []
        if not current_holdings.empty:
            valid_holdings = \
            current_holdings[(current_holdings['Quantity'] > 0) & (current_holdings['Type'] == 'STOCK')][
                'Symbol'].tolist()

        with st.form("add_stock_form"):
            c1, c2 = st.columns(2)
            t_date = c1.date_input("日期", date.today())

            t_sym = ""
            if is_sell:
                if valid_holdings:
                    t_sym = c2.selectbox("选择持仓股票", valid_holdings)
                    holding_qty = current_holdings[current_holdings['Symbol'] == t_sym]['Quantity'].values[0]
                    st.caption(f"💡 可卖持仓: {int(holding_qty)} 股")
                else:
                    c2.warning("无持仓可卖")
            else:
                t_sym = c2.text_input("代码", "NVDA").upper()

            c3, c4 = st.columns(2)
            t_qty = c3.number_input("数量 (股)", 1.0, step=100.0)
            t_price = c4.number_input("成交单价", 0.0, step=0.1)
            c5, c6 = st.columns(2)
            t_fee = c5.number_input("佣金", 0.0)
            t_note = c6.text_input("笔记", placeholder="策略备注")

            if st.form_submit_button("提交交易", use_container_width=True):
                final_type = "SELL" if is_sell else "BUY"
                if is_sell and not t_sym:
                    st.error("请选择股票")
                elif is_sell and t_qty > holding_qty:
                    st.error("数量超过持仓")
                else:
                    db.add_transaction(t_date, t_sym, final_type, t_qty, t_price, t_fee, t_note, asset_category='STOCK',
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

# 1. 大师语录
quotes = [
    ("流水不争先，争的是滔滔不绝。", "道德经"),
    ("股市是财富从急躁人手中转移到耐心人手中的工具。", "沃伦·巴菲特"),
    ("如果你不愿意拥有一只股票十年，那就不要考虑拥有它十分钟。", "沃伦·巴菲特"),
    ("要赚大钱，不是靠买卖，而是靠等待。", "查理·芒格"),
    ("反过来想，总是反过来想。", "查理·芒格"),
    ("长期看，股票的回报率取决于企业的盈利增长。", "彼得·林奇"),
    ("悲观者正确，乐观者赚钱。", "投资箴言")
]
daily_quote = random.choice(quotes)
st.markdown(f"""<div class="quote-card">“{daily_quote[0]}”<div class="quote-author">—— {daily_quote[1]}</div></div>""",
            unsafe_allow_html=True)

st.subheader("🔭 长期主义驾驶舱 (USD Base)")

# --- 2. 宏观模块 (UI魔改版) ---
macro_data = get_global_macro_data()

# 开关按钮
col_switch, _ = st.columns([1, 4])
with col_switch:
    market_mode = st.radio("Market View", ["🇺🇸 美股气候", "🇨🇳 中国资产"], horizontal=True, label_visibility="collapsed")

mc1, mc2 = st.columns(2)

if "美股" in market_mode:
    # 🇺🇸 US
    vix, tnx = macro_data['vix'], macro_data['tnx']

    vix_str = f"{vix:.2f}" if vix else "N/A"
    vix_delta, vix_label = "off", "市场情绪"
    if vix:
        if vix < 15:
            vix_delta, vix_label = "inverse", "贪婪 (风险)"
        elif vix > 30:
            vix_delta, vix_label = "normal", "恐慌 (机会)"

    mc1.metric("🌊 VIX 恐慌指数 (US)", vix_str, vix_label, delta_color=vix_delta)

    tnx_str = f"{tnx:.2f}%" if tnx else "N/A"
    mc2.metric("⚓ 10年美债收益率", tnx_str, "全球资产锚", delta_color="off")

else:
    # 🇨🇳 CN/HK
    vhsi, cnh = macro_data['vhsi'], macro_data['cnh']

    vhsi_str = f"{vhsi:.2f}" if vhsi else "N/A"
    vhsi_delta, vhsi_label = "off", "市场情绪"
    if vhsi:
        if vhsi > 30:
            vhsi_delta, vhsi_label = "normal", "恐慌 (黄金坑)"
        elif vhsi < 15:
            vhsi_delta, vhsi_label = "inverse", "贪婪 (风险)"

    mc1.metric("📉 恒指波幅 (VHSI)", vhsi_str, vhsi_label, delta_color=vhsi_delta)

    cnh_str = f"{cnh:.4f}" if cnh else "N/A"
    cnh_delta, cnh_label = "off", "汇率波动"
    if cnh:
        if cnh > 7.25:
            cnh_delta, cnh_label = "inverse", "贬值 (压力)"
        elif cnh < 6.9:
            cnh_delta, cnh_label = "normal", "升值 (流入)"

    mc2.metric("💱 美元/离岸人民币", cnh_str, cnh_label, delta_color=cnh_delta)

st.markdown("---")

# --- 3. 个人资产计算 ---
portfolio_df = db.get_portfolio_summary()
total_invested = db.get_total_invested()
cash_balance = db.get_cash_balance()

market_val_usd = 0
total_cost_usd = 0
max_days_held = 0
highest_badge_icon = "🌱"
highest_badge_name = "新手"

if not portfolio_df.empty:
    if 'last_update' not in st.session_state:
        portfolio_df = update_portfolio_valuation(portfolio_df)
        st.session_state['portfolio_cache'] = portfolio_df
        st.session_state['last_update'] = datetime.now()
    else:
        portfolio_df = st.session_state['portfolio_cache']

    market_val_usd = portfolio_df['Market Value'].sum()
    total_cost_usd = portfolio_df['Total Cost'].sum()

    if 'Days Held' in portfolio_df.columns and not portfolio_df['Days Held'].isnull().all():
        max_days_held = portfolio_df['Days Held'].max()
        highest_badge_icon, highest_badge_name = get_badge_info(max_days_held)

# 渲染右上角勋章
st.markdown(f"""
<div class="badge-container">
    <div class="badge-icon">{highest_badge_icon}</div>
    <div class="badge-text">
        {highest_badge_name}
        <div class="badge-label">坚持 {int(max_days_held)} 天</div>
    </div>
</div>
""", unsafe_allow_html=True)

# 净资产计算
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
c1.metric("⚖️ 杠杆率", f"{lev_ratio:.2f}x", delta="安全" if lev_ratio <= 1.2 else "偏高",
          delta_color="inverse" if lev_ratio > 1.2 else "normal")
c2.metric("🎯 Top3 集中度", f"{top3_conc:.1f}%")
c3.metric("🔫 现金/负债", f"${abs(cash_balance):,.0f}", f"{cash_ratio:+.1f}%")
c4.metric("🛡️ 利润安全垫", f"${pnl:,.0f}")

st.write("")
st.caption("📈 财富复利曲线 (Total Equity Curve)")
history_df = db.get_history_data()
render_history_chart(history_df)

st.divider()

# --- 5. 多维透视 ---
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
                render_echarts_pie(valid_pie, 'Symbol', 'Market Value')
            else:
                st.info("无数据")
        with chart_tab2:
            if not valid_pie.empty:
                sec_df = valid_pie.groupby('Sector')['Market Value'].sum().reset_index()
                render_echarts_pie(sec_df, 'Sector', 'Market Value')
            else:
                st.info("无数据")
        with chart_tab3:
            if not valid_pie.empty:
                curr_df = valid_pie.groupby('Currency')['Market Value'].sum().reset_index()
                render_echarts_pie(curr_df, 'Currency', 'Market Value')
            else:
                st.info("无数据")

    with col_r:
        st.caption("持仓明细 (自动折算 USD)")
        portfolio_df['PnL $'] = portfolio_df['Market Value'] - portfolio_df['Total Cost']
        portfolio_df['Safety Margin'] = portfolio_df.apply(
            lambda x: max(0, (x['Price'] - x['Avg Cost']) / x['Price'] * 100) if x['Price'] > 0 and x[
                'Type'] == 'STOCK' else 0, axis=1
        )
        portfolio_df['Badge'] = portfolio_df['Days Held'].apply(
            lambda d: get_badge_info(d)[0] + " " + get_badge_info(d)[1])

        display_df = portfolio_df.sort_values('Market Value', ascending=False)

        st.dataframe(
            display_df,
            column_order=["Sector", "Symbol", "Quantity", "Avg Cost", "Price", "Market Value", "Safety Margin", "Badge",
                          "Days Held"],
            column_config={
                "Sector": st.column_config.TextColumn("赛道", width="small"),
                "Symbol": st.column_config.TextColumn("代码", width="small"),
                "Quantity": st.column_config.NumberColumn("持仓", format="%.0f"),
                "Avg Cost": st.column_config.NumberColumn("成本", format="%.2f"),
                "Price": st.column_config.NumberColumn("现价", format="%.2f"),
                "Market Value": st.column_config.NumberColumn("市值", format="$%.0f"),
                "Safety Margin": st.column_config.ProgressColumn("安全边际", format="%.1f%%", min_value=0,
                                                                 max_value=100),
                "Badge": st.column_config.TextColumn("荣誉", width="small"),
                "Days Held": st.column_config.NumberColumn("天数", format="%d")
            },
            use_container_width=True, height=450, hide_index=True
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