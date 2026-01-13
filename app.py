import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
from datetime import date, datetime
import data_manager as db
from streamlit_option_menu import option_menu

# ================= 1. 页面配置与 CSS =================
st.set_page_config(page_title="我的投资管理 Pro", layout="wide")
db.init_db()

st.markdown("""
<style>
    /* ================= 1. 全局表格样式 ================= */
    th, td { text-align: center !important; }
    .stDataFrame { text-align: center !important; }
    div[data-testid="stDataEditor"] div[role="grid"] { text-align: center !important; }

    /* ================= 2. 极简固定侧边栏 (Gemini Style) ================= */

    /* 1. 锁定侧边栏宽度 */
    section[data-testid="stSidebar"] {
        min-width: 80px !important;
        max-width: 80px !important;
    }

    /* 2. 隐藏侧边栏原本的折叠按钮 (X) 和 顶部的装饰条 */
     div[data-testid="collapsedControl"] {
        display: none;
    }
    /* 3. 关键：去除侧边栏内部容器的所有内边距，实现“满宽”效果 */
    section[data-testid="stSidebar"] .block-container {
        padding: 0 !important;
        padding-top: 2rem !important; /* 顶部留白 */
        margin: 0 !important;
        max-width: 60px !important;
    }

    /* 3. 去掉侧边栏右侧的边框线，让它更像一个整体 (可选) */
   section[data-testid="stSidebar"] .block-container {
        padding-top: 2rem;
        padding-left: 0 !important;
        padding-right: 0 !important;
        margin: 0 !important;
    }
    
    header[data-testid="stHeader"] {
        # display: none;
    }
    
    /* ================= Calendar & Chart Styles (New) ================= */
    
    /* 1. 顶部筛选丸 (Pills) */
    .filter-pills { display: flex; gap: 8px; margin-bottom: 15px; overflow-x: auto; padding-bottom: 5px; }
    .filter-pill {
        padding: 5px 15px; border-radius: 15px; background: #f0f2f6; color: #555; 
        font-size: 13px; cursor: pointer; border: 1px solid transparent; transition: all 0.2s; white-space: nowrap;
    }
    .filter-pill:hover { background: #e0e0e0; }
    .filter-pill.active { background: #fff; border-color: #ddd; color: #000; font-weight: bold; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }

    /* 2. 日历格子样式 */
    .cal-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 6px; margin-top: 10px; }
    
    .cal-header-cell { text-align: center; color: #999; font-size: 12px; padding-bottom: 5px; }
    
    .cal-cell {
        aspect-ratio: 1/0.85; border-radius: 6px; background: #fff;
        display: flex; flex-direction: column; align-items: center; justify-content: center;
        font-size: 12px; position: relative; border: 1px solid #f9f9f9;
    }
    .cal-day-num { font-size: 14px; color: #333; margin-bottom: 2px; font-weight: 500; }
    .cal-val { font-size: 10px; font-weight: 500; zoom: 0.9; }
    
    /* 3. 颜色定义 (红涨绿跌, 浅底深字) */
    .bg-up { background-color: #fff1f0 !important; border-color: #ffd6d6 !important; }
    .text-up { color: #d93025 !important; }
    
    .bg-down { background-color: #e6f4ea !important; border-color: #ceead6 !important; }
    .text-down { color: #1e8e3e !important; }
    
    .bg-gray { background-color: #f8f9fa !important; color: #ccc !important; }

    /* 4. 周/月/年视图卡片 */
    .period-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-top: 10px; }
    .period-card { padding: 12px; border-radius: 8px; text-align: center; border: 1px solid #eee; background: white; }
    

    /* ================= 3. 弹窗与悬浮按钮 ================= */
    div[data-testid="stDialog"] div.stButton { position: static !important; width: auto !important; }
    div[data-testid="stDialog"] button { 
        border-radius: 4px !important; width: auto !important; height: auto !important; 
        font-size: 1rem !important; box-shadow: none !important; 
    }

    /* 悬浮按钮定位 */
    span#fab-anchor + div.stButton {
        position: fixed; bottom: 40px; right: 40px; z-index: 9999; width: auto;
    }
    span#fab-anchor + div.stButton > button {
        border-radius: 50%; width: 60px; height: 60px; font-size: 30px;
        background-color: #FF4B4B; color: white; box-shadow: 2px 2px 10px rgba(0,0,0,0.3);
        border: none; padding: 0; display: flex; align-items: center; justify-content: center;
    }
    span#fab-anchor + div.stButton > button:hover { background-color: #FF2B2B; }
</style>
""", unsafe_allow_html=True)


# ================= 2. 工具函数 =================
def get_realtime_price(symbol):
    """获取实时价格 (仅支持股票, 期权暂不支持实时)"""
    symbol = symbol.lower().strip()
    headers = {'Referer': 'https://finance.sina.com.cn'}
    try:
        # 简单判断：带空格的通常是我们拼接的期权代码，不去查价
        if ' ' in symbol: return None

        if symbol.isalpha():  # 美股
            url = f"https://hq.sinajs.cn/list=gb_{symbol}"
            resp = requests.get(url, headers=headers)
            content = resp.text.split('="')[1].split(',')
            if len(content) > 1: return float(content[1])
        else:  # A股
            if not (symbol.startswith('sh') or symbol.startswith('sz')):
                prefix = 'sh' if symbol.startswith('6') else 'sz'
                symbol = prefix + symbol
            url = f"https://hq.sinajs.cn/list={symbol}"
            resp = requests.get(url, headers=headers)
            content = resp.text.split('="')[1].split(',')
            if len(content) > 3: return float(content[3])
    except:
        return None
    return None


def update_and_save_snapshot():
    """强制重新计算当前净值并保存到数据库"""
    # 1. 获取基础数据
    portfolio_df = db.get_portfolio_summary()
    total_invested_funds = db.get_total_invested()
    cash_balance = db.get_cash_balance()

    # 2. 计算持仓市值
    market_value_total = 0
    total_holdings_cost = 0

    if not portfolio_df.empty:
        # 这里为了速度，不显示进度条，直接计算
        for _, row in portfolio_df.iterrows():
            if row['Type'] == 'STOCK':
                # 注意：这里做个容错，优先用 Raw Symbol，没有则用 Symbol
                sym = row.get('Raw Symbol', row['Symbol'])
                price = get_realtime_price(sym)
                if price is None: price = 0
            else:
                price = 0  # 期权暂按0或成本计算

            market_value_total += price * row['Quantity'] * row['Multiplier']
            total_holdings_cost += row['Total Cost']

    # 3. 计算总资产 (复用智能会计逻辑)
    if total_invested_funds > 0:
        final_total_asset = market_value_total + cash_balance
        final_invested = total_invested_funds
    else:
        final_total_asset = market_value_total
        final_invested = total_holdings_cost if total_holdings_cost > 0 else 1

    # 4. 保存到数据库 (覆盖今日旧数据)
    today_str = date.today().strftime('%Y-%m-%d')
    db.save_daily_snapshot(today_str, final_total_asset, final_invested)

    return final_total_asset, final_invested

# ================= 3. 弹窗逻辑 (修复缩进 + 补全资金记录) =================
@st.dialog("📝 操作中心")
def show_add_modal():
    # 调整顺序：股票 -> 期权 -> 资金 -> 回收站
    tab1, tab2, tab3, tab4 = st.tabs(["股票交易", "期权交易", "资金进出", "♻️ 回收站"])

    # --- Tab 1: 股票 ---
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
                db.add_transaction(t_date, t_sym, t_type, t_qty, t_price, t_fee, t_note,
                                   asset_category='STOCK', multiplier=1)
                st.success("已保存")
                st.rerun()

    # --- Tab 2: 期权 ---
    with tab2:
        st.caption("💡 提示：期权合约乘数默认为 100")
        with st.form("add_option_form"):
            c1, c2 = st.columns(2)
            o_date = c1.date_input("交易日期", date.today())
            o_sym = c2.text_input("正股代码", "NVDA").upper()

            c3, c4, c5 = st.columns(3)
            o_exp = c3.date_input("到期日")
            o_strike = c4.number_input("行权价", 0.0, step=5.0)
            o_type = c5.selectbox("类型", ["CALL", "PUT"])

            c6, c7 = st.columns(2)
            o_side = c6.selectbox("方向", ["BUY", "SELL"], help="Buy: 买入开仓/平仓; Sell: 卖出开仓/平仓")
            o_qty = c7.number_input("张数 (Contract)", 1.0, step=1.0)

            c8, c9 = st.columns(2)
            o_price = c8.number_input("权利金单价", 0.0, step=0.1)
            o_fee = c9.number_input("佣金", 0.0)

            if st.form_submit_button("提交期权交易", use_container_width=True):
                db.add_transaction(
                    date=o_date, symbol=o_sym, trans_type=o_side,
                    quantity=o_qty, price=o_price, fee=o_fee, note=f"Option {o_type} {o_strike}",
                    asset_category='OPTION', multiplier=100,
                    strike=o_strike, expiration=str(o_exp), option_type=o_type
                )
                st.success("期权交易已保存")
                st.rerun()

    # --- Tab 3: 资金管理 (修复：移出 Tab 2 内部，并增加历史记录) ---
    with tab3:
        mode = st.selectbox("操作模式", ["资金流水", "余额校准"], label_visibility="collapsed")

        # 1. 操作区域
        if mode == "资金流水":
            with st.form("fund_form"):
                f_date = st.date_input("日期", date.today())
                c1, c2 = st.columns(2)
                f_type = c1.selectbox("类型", ["DEPOSIT", "WITHDRAW"],
                                      format_func=lambda x: "入金" if x == "DEPOSIT" else "出金")
                f_amount = c2.number_input("金额 ($)", 1000.0, step=100.0)
                f_note = st.text_input("备注", placeholder="选填")

                if st.form_submit_button("提交", use_container_width=True):
                    db.add_fund_flow(f_date, f_type, f_amount, f_note)
                    st.success("已记录")
                    st.rerun()

        else:  # 余额校准
            curr_cash = db.get_cash_balance()
            with st.form("fix_balance_form"):
                st.markdown(
                    f"<div style='text-align:center; color:#888; font-size:12px; margin-bottom:10px;'>系统浮存金: <b>${curr_cash:,.2f}</b></div>",
                    unsafe_allow_html=True)

                c1, c2 = st.columns(2)
                target_date = c1.date_input("校准日期", date.today())
                target_val = c2.number_input("实际余额 ($)", value=float(curr_cash), step=100.0)

                if st.form_submit_button("执行校准", type="primary", use_container_width=True):
                    db.set_cash_balance(target_val, target_date)
                    st.success(f"余额已校准为 ${target_val:,.2f}")
                    st.rerun()

        # 2. 历史记录区域 (补回)
        st.divider()
        st.caption("📜 资金流水记录")
        fund_df = db.get_fund_flows()
        if not fund_df.empty:
            edited_funds = st.data_editor(
                fund_df,
                column_config={
                    "id": None, "date": "日期",
                    "type": st.column_config.TextColumn("类型", width="small"),
                    "amount": st.column_config.NumberColumn("金额", format="$%.2f"),
                    "note": "备注"
                },
                hide_index=True, use_container_width=True, num_rows="dynamic", key="fund_editor_widget"
            )
            if st.session_state.get("fund_editor_widget"):
                changes = st.session_state["fund_editor_widget"]
                if changes.get("deleted_rows"):
                    for idx in changes["deleted_rows"]:
                        try:
                            db.delete_fund_flow(fund_df.iloc[idx]['id'])
                        except:
                            pass
                    st.rerun()
        else:
            st.info("暂无资金记录")

    # --- Tab 4: 回收站 ---
    with tab4:
        st.caption("最近 7 天删除的记录")
        deleted_df = db.get_deleted_transactions_last_7_days()
        if not deleted_df.empty:
            st.markdown(
                """<div style="display: flex; color: #666; font-size: 12px; margin-bottom: 10px; border-bottom: 1px solid #eee; padding-bottom: 5px;"><span style="flex: 1;">交易详情</span><span style="width: 60px; text-align: right;">操作</span></div>""",
                unsafe_allow_html=True)
            for idx, row in deleted_df.iterrows():
                c_info, c_btn = st.columns([4.5, 1], vertical_alignment="center")
                with c_info:
                    type_color = "#d9534f" if row['type'] == 'BUY' else "#5cb85c"
                    cat_label = "OPT" if row.get('asset_category') == 'OPTION' else "STK"
                    st.markdown(f"""
                        <div style="font-size: 14px;">
                            <span style="color: #888;">{row['date']}</span>
                            <span style="background:#eee; padding:1px 4px; font-size:10px; border-radius:3px;">{cat_label}</span>
                            <strong>{row['symbol']}</strong> 
                            <span style="color:{type_color}; font-weight:bold;">{row['type']}</span>
                            <span>({int(row['quantity'])})</span>
                        </div>""", unsafe_allow_html=True)
                with c_btn:
                    if st.button("恢复", key=f"rst_{row['id']}", type="primary", use_container_width=True):
                        db.restore_transaction(row['id'])
                        st.rerun()
                st.markdown("<hr style='margin: 4px 0; border: 0; border-top: 1px dashed #f0f0f0;'>",
                            unsafe_allow_html=True)
        else:
            st.info("回收站是空的")


with st.sidebar:
    selected_option = option_menu(
        menu_title=None,
        options=["资产看板", "收益日历"],
        # 使用 Bootstrap Icons:
        # 'grid-fill' -> 类似 Gemini 的应用方块
        # 'calendar-range' -> 日历
        icons=["grid-fill", "calendar-range"],
        default_index=0,
        orientation="vertical",
        styles={
            "container": {
                "padding": "5px !important", # 容器微调
                "background-color": "transparent"
            },
            "icon": {
                "color": "#444746", # Google 深灰
                "font-size": "24px", # 图标大小
                "margin": "0px"      # 强制去掉图标边距
            },
            "nav-link": {
                "font-size": "0px", # 隐藏文字
                "text-align": "center",
                "margin": "8px 0px", # 按钮垂直间距
                "padding": "0px",    # 内部padding清零，靠flex居中
                "height": "48px",    # 固定高度，接近正方形
                "width": "100%",     # 填满侧边栏宽度
                "border-radius": "12px", # 圆角矩形
                "display": "flex",   # 开启 Flex 布局
                "align-items": "center",     # 垂直居中
                "justify-content": "center", # 水平居中
                "--hover-color": "#f0f2f5"   # 悬停浅灰
            },
            "nav-link-selected": {
                "background-color": "#d3e3fd", # 选中背景：Google 浅蓝 (Gemini风格) 或改成 #e0e0e0 (纯灰)
                "color": "#041e49",            # 选中图标色
            },
        }
    )

# 逻辑映射
page = selected_option

# ================= 5. 主页面 =================
if page == "资产看板":
    st.subheader("🏠 资产总览")

    # 1. 获取所有基础数据
    portfolio_df = db.get_portfolio_summary()
    total_invested_funds = db.get_total_invested()  # 从资金流水表获取的真实本金
    cash_balance = db.get_cash_balance()  # 实时浮存金

    # 2. 计算最新的持仓市值
    market_value_total = 0
    total_holdings_cost = 0  # 纯持仓的成本

    if not portfolio_df.empty:
        if 'last_update' not in st.session_state:
            p_bar = st.progress(0, text="更新行情...")
            current_prices = []
            mkt_values = []

            for i, row in portfolio_df.iterrows():
                # 只有股票查价，期权用0或成本价
                if row['Type'] == 'STOCK':
                    price = get_realtime_price(row['Raw Symbol'])
                    if price is None: price = 0
                else:
                    price = 0

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

    # ================= 核心修正：智能收益率计算 =================

    # 场景 A: 标准会计模式 (你录入了入金记录)
    if total_invested_funds > 0:
        # 总资产 = 持仓市值 + 现金 (现金可能是负的，如果透支买股)
        final_total_asset = market_value_total + cash_balance
        final_invested = total_invested_funds
        final_pnl = final_total_asset - final_invested
        calc_mode_desc = "基于账户总权益 (Asset based)"

    # 场景 B: 偷懒模式 (没录入入金，或者入金被出金抵消了)
    # 此时回退到“只看持仓盈亏”，忽略现金流
    else:
        final_total_asset = market_value_total
        final_invested = total_holdings_cost
        final_pnl = market_value_total - total_holdings_cost
        # 如果连持仓都没有，避免除以0
        if final_invested == 0: final_invested = 1
        calc_mode_desc = "仅基于持仓涨跌 (Holdings based)"

    # 计算收益率
    ret_rate = (final_pnl / final_invested * 100)

    # 自动保存快照 (逻辑不变，只是确保每次刷新都保存)
    db.save_daily_snapshot(date.today().strftime('%Y-%m-%d'), final_total_asset, final_invested)

    # 3. 顶部 KPI 卡片
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("总资产", f"${final_total_asset:,.0f}", help=f"计算模式: {calc_mode_desc}")

    # 显示浮存金 (如果是偷懒模式，现金可能是负数，但这不影响上面的总资产显示)
    c2.metric("浮存金", f"${cash_balance:,.0f}", help="可用资金")

    c3.metric("总收益", f"${final_pnl:,.0f}", delta_color="normal")
    c4.metric("总收益率", f"{ret_rate:.2f}%", delta=f"{ret_rate:.2f}%")
    st.divider()

    # 4. 图表与表格
    if not portfolio_df.empty:
        col_chart1, col_chart2 = st.columns(2)
        with col_chart1:
            st.caption("股票持仓分布 (不含期权)")
            # 过滤掉市值为0的(主要是期权)
            valid_df = portfolio_df[portfolio_df['Market Value'] > 0]
            if not valid_df.empty:
                fig = px.pie(valid_df, values='Market Value', names='Symbol', hole=0.5)
                fig.update_layout(margin=dict(t=0, b=0, l=0, r=0))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("暂无股票持仓市值")
        with col_chart2:
            st.caption("持仓明细 (含期权)")
            # 格式化显示
            display_df = portfolio_df[['Symbol', 'Quantity', 'Avg Cost', 'Price', 'Market Value', 'Type']].copy()
            st.dataframe(
                display_df.style.format({
                    "Avg Cost": "{:.2f}",
                    "Price": "{:.2f}",
                    "Market Value": "{:.0f}"
                }), use_container_width=True, height=300
            )
    else:
        st.info("暂无持仓，请点击右下角 ➕ 添加交易。")

    # 交易流水
    st.subheader("📋 交易流水")
    all_trans = db.get_all_transactions(include_deleted=False)
    if not all_trans.empty:
        cols = ['id', 'date', 'symbol', 'type', 'quantity', 'price', 'fee', 'note', 'asset_category']
        if 'asset_category' not in all_trans.columns: all_trans['asset_category'] = 'STOCK'
        if 'note' not in all_trans.columns: all_trans['note'] = ""

        display_trans = all_trans[cols].copy()
        edited_df = st.data_editor(
            display_trans,
            column_config={
                "id": None,
                "asset_category": st.column_config.TextColumn("类别", width="small"),
                "date": "日期", "symbol": "代码", "type": "方向",
                "quantity": st.column_config.NumberColumn("数量", format="%.0f"),
                "price": st.column_config.NumberColumn("价格", format="%.2f"),
                "fee": st.column_config.NumberColumn("费用", format="%.1f"),
                "note": "笔记"
            },
            hide_index=True, use_container_width=True, num_rows="dynamic", key="trans_editor_widget"
        )
        if st.session_state.get("trans_editor_widget"):
            changes = st.session_state["trans_editor_widget"]
            if changes.get("deleted_rows"):
                for idx in changes["deleted_rows"]:
                    try:
                        db.soft_delete_transaction(int(display_trans.iloc[idx]['id']))
                    except:
                        pass
                if 'last_update' in st.session_state: del st.session_state['last_update']
                st.rerun()

elif page == "收益日历":
    st.subheader("📅 收益复盘 (USD)")
    import calendar

    history_df = db.get_history_data()

    if not history_df.empty:
        # --- 1. 数据清洗与计算 (修复版) ---
        history_df['date'] = pd.to_datetime(history_df['date'])
        history_df = history_df.sort_values('date')

        # 计算当日盈亏 (Daily PnL)
        history_df['daily_profit'] = history_df['total_pnl'].diff().fillna(0)
        # 第一天修正：如果只有一天，diff是NaN，直接用total_pnl
        if len(history_df) >= 1:
            history_df.iloc[0, history_df.columns.get_loc('daily_profit')] = history_df.iloc[0]['total_pnl']

        # 计算累计收益率 (Total Return %) = 总盈亏 / 总投入
        # 避免分母为0
        history_df['total_cost_safe'] = history_df['total_cost'].replace(0, 1)
        history_df['cum_pct'] = (history_df['total_pnl'] / history_df['total_cost_safe'] * 100).fillna(0)

        # 计算日度收益率 (Daily Return %) = 当日盈亏 / 昨日总资产
        history_df['prev_asset'] = history_df['total_asset'].shift(1).fillna(history_df['total_cost'])  # 修复KeyError
        history_df['prev_asset'] = history_df['prev_asset'].replace(0, 1)
        history_df['daily_pct'] = (history_df['daily_profit'] / history_df['prev_asset'] * 100).fillna(0)

        # 时间维度
        history_df['year'] = history_df['date'].dt.year
        history_df['month'] = history_df['date'].dt.month
        history_df['day'] = history_df['date'].dt.day
        history_df['week'] = history_df['date'].dt.isocalendar().week

        # ==========================================
        # 模块 A: 收益率曲线 (优先展示)
        # ==========================================
        with st.container(border=True):
            c_chart_h1, c_chart_h2 = st.columns([1, 4], vertical_alignment="center")
            c_chart_h1.markdown("#### 📈 趋势分析")

            # 曲线图切换控制
            with c_chart_h2:
                # 把切换按钮挤到右边
                _, c_sub = st.columns([3, 1])
                with c_sub:
                    curve_metric = st.radio("Curve", ["累计收益率 %", "累计盈亏 $"], horizontal=True,
                                            label_visibility="collapsed", key="curve_select")

            # 绘图数据准备
            if "收益率" in curve_metric:
                plot_y = 'cum_pct'
                y_title = "累计收益率 (%)"
                hover_temp = "日期: %{x}<br>收益率: %{y:.2f}%"
                line_color = '#2962ff'  # 蓝色曲线
            else:
                plot_y = 'total_pnl'
                y_title = "累计盈亏 ($)"
                hover_temp = "日期: %{x}<br>盈亏: $%{y:,.0f}"
                line_color = '#ff4b4b'  # 红色曲线

            # 绘制 Plotly 曲线
            fig = px.line(history_df, x='date', y=plot_y)
            fig.update_traces(line_color=line_color, line_width=2.5, hovertemplate=hover_temp)
            fig.update_layout(
                margin=dict(l=10, r=10, t=10, b=10),
                height=280,
                xaxis_title="",
                yaxis_title="",
                showlegend=False,
                hovermode="x unified",
                plot_bgcolor='rgba(0,0,0,0)',
                xaxis=dict(showgrid=False),
                yaxis=dict(showgrid=True, gridcolor='#eee')
            )
            st.plotly_chart(fig, use_container_width=True)

        # ==========================================
        # 模块 B: 收益日历 (仿参考图样式)
        # ==========================================
        st.write("")  # Spacer

        # 1. 顶部筛选 (Mockup)
        st.markdown("""
            <div class="filter-pills">
                <div class="filter-pill">本月</div>
                <div class="filter-pill">近3月</div>
                <div class="filter-pill active">本年</div>
                <div class="filter-pill">全部</div>
            </div>
        """, unsafe_allow_html=True)

        # 2. 控制栏
        c_ctrl1, c_ctrl2 = st.columns([1, 2], vertical_alignment="center")
        with c_ctrl1:
            # 年份选择
            years = sorted(history_df['year'].unique(), reverse=True)
            sel_year = st.selectbox("Year", years, label_visibility="collapsed", key="cal_year")
        with c_ctrl2:
            # 视图与指标切换
            sc1, sc2 = st.columns(2)
            view_mode = sc1.radio("View", ["日", "周", "月", "年"], horizontal=True, label_visibility="collapsed",
                                  key="cal_view")
            cal_metric = sc2.radio("Metric", ["收益额", "收益率"], horizontal=True, label_visibility="collapsed",
                                   key="cal_metric")

        # 3. 渲染逻辑
        is_pct_mode = (cal_metric == "收益率")
        current_data = history_df[history_df['year'] == sel_year]


        # 辅助样式函数
        def get_style(val):
            txt = f"{val:+.2f}%" if is_pct_mode else f"${val:+,.0f}"
            if val == 0: return "bg-gray", txt
            css = "bg-up text-up" if val > 0 else "bg-down text-down"
            return css, txt


        if current_data.empty:
            st.info(f"{sel_year} 年暂无数据")

        # --- 日视图 ---
        elif view_mode == "日":
            latest_month = current_data['month'].max()
            months = sorted(current_data['month'].unique(), reverse=True)
            sel_month = st.pills("月份", months, default=latest_month, selection_mode="single") or latest_month

            # 准备数据
            month_df = current_data[current_data['month'] == sel_month].set_index('day')
            calendar.setfirstweekday(calendar.SUNDAY)
            cal_matrix = calendar.monthcalendar(sel_year, sel_month)
            weekdays = ["日", "一", "二", "三", "四", "五", "六"]

            # 渲染表头
            cols = st.columns(7)
            for i, d in enumerate(weekdays):
                cols[i].markdown(f"<div class='cal-header-cell'>{d}</div>", unsafe_allow_html=True)

            # 渲染网格
            html = '<div class="cal-grid">'
            for week in cal_matrix:
                for day in week:
                    if day == 0:
                        html += '<div class="cal-cell" style="background:transparent; border:none;"></div>'
                    else:
                        val = 0
                        if day in month_df.index:
                            val = month_df.loc[day]['daily_pct'] if is_pct_mode else month_df.loc[day]['daily_profit']

                        css, txt = get_style(val)
                        # 如果没有交易数据 (val=0)，显示灰色
                        if val == 0 and day not in month_df.index:
                            html += f'<div class="cal-cell"><div class="cal-day-num" style="color:#ddd">{day}</div></div>'
                        else:
                            html += f'<div class="cal-cell {css}"><div class="cal-day-num">{day}</div><div class="cal-val">{txt}</div></div>'
            html += '</div>'
            st.markdown(html, unsafe_allow_html=True)

        # --- 周视图 ---
        elif view_mode == "周":
            col = 'daily_profit'  # 周视图通常看金额汇总
            weekly = current_data.groupby('week')[col].sum().sort_index(ascending=False)
            html = '<div class="period-grid">'
            for wk, val in weekly.items():
                css, txt = get_style(val)  # 这里复用样式，注意如果是收益率模式，周度简单加总是错误的，建议周视图强制显示金额
                # 强制周视图显示金额
                if is_pct_mode:
                    txt = "N/A"
                else:
                    txt = f"${val:+,.0f}"

                html += f"""
                <div class="period-card {css}">
                    <div style="font-size:12px; color:#888;">第{wk}周</div>
                    <div style="font-size:18px; font-weight:600; margin-top:5px;">{txt}</div>
                </div>"""
            html += '</div>'
            st.markdown(html, unsafe_allow_html=True)
            if is_pct_mode: st.caption("注：周视图暂只支持查看收益额")

        # --- 月视图 ---
        elif view_mode == "月":
            monthly = current_data.groupby('month')['daily_profit'].sum()
            html = '<div class="period-grid">'
            for m in range(1, 13):
                val = monthly.get(m, 0)
                css, txt = "bg-gray", "-"
                if val != 0:
                    css = "bg-up text-up" if val > 0 else "bg-down text-down"
                    txt = f"${val:+,.0f}"

                html += f"""
                <div class="period-card {css}">
                    <div style="font-size:16px; font-weight:bold; margin-bottom:4px;">{m}月</div>
                    <div style="font-size:13px;">{txt}</div>
                </div>"""
            html += '</div>'
            st.markdown(html, unsafe_allow_html=True)

        # --- 年视图 ---
        elif view_mode == "年":
            yearly = history_df.groupby('year')['daily_profit'].sum().sort_index(ascending=False)
            html = '<div class="period-grid" style="grid-template-columns: repeat(2, 1fr);">'
            for yr, val in yearly.items():
                css = "bg-up text-up" if val > 0 else "bg-down text-down"
                txt = f"${val:+,.0f}"
                html += f"""
                <div class="period-card {css}">
                    <div style="font-size:24px; font-weight:bold;">{yr}</div>
                    <div style="font-size:18px; margin-top:8px;">{txt}</div>
                </div>"""
            html += '</div>'
            st.markdown(html, unsafe_allow_html=True)

    else:
        st.warning("暂无历史数据，请积累几天数据后再来查看。")

# ================= 6. 悬浮按钮 (终极修复版) =================
st.markdown('<span id="fab-anchor"></span>', unsafe_allow_html=True)
if st.button("➕", key="fab_main"):
    show_add_modal()

st.markdown("""
<style>
    /* 1. 悬浮按钮核心样式 (仅针对页面底部的这个特定按钮) */
    div.stButton:has(button:active), div.stButton:last-of-type {
        position: fixed;
        bottom: 40px;
        right: 40px;
        z-index: 9999;
        width: auto;
    }

    div.stButton:last-of-type > button {
        border-radius: 50%;
        width: 60px;
        height: 60px;
        font-size: 24px;
        background-color: #FF4B4B;
        color: white;
        box-shadow: 0px 4px 10px rgba(0,0,0,0.3);
        border: none;
    }

    /* === 关键修复：保护弹窗(Dialog)里的按钮不受上面样式影响 === */
    div[data-testid="stDialog"] div.stButton {
        position: static !important; /* 还原定位 */
        width: auto !important;
    }

    div[data-testid="stDialog"] button {
        border-radius: 4px !important; /* 还原圆角 */
        width: auto !important;        /* 还原宽度 */
        height: auto !important;       /* 还原高度 */
        font-size: 1rem !important;    /* 还原字体 */
        box-shadow: none !important;   /* 去掉阴影 */
        /* 下面这行确保它不强制变红，除非它是 type='primary' */
        /* background-color: transparent; */ 
    }
</style>
""", unsafe_allow_html=True)