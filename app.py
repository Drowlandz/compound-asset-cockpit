import streamlit as st
import pandas as pd
from datetime import date, datetime
import data_manager as db
import config as cf
import utils as ut
import ui

# ================= 1. 初始化 =================
st.set_page_config(page_title="长期主义资产管理", layout="wide", page_icon="🔭")
db.init_db()
st.markdown(cf.CUSTOM_CSS, unsafe_allow_html=True)

if 'privacy_mode' not in st.session_state:
    st.session_state['privacy_mode'] = False


def is_privacy_mode():
    return bool(st.session_state.get('privacy_mode', False))


def fmt_money(value, decimals=0):
    if is_privacy_mode():
        return "****"
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = 0.0
    return f"${number:,.{decimals}f}"


def money_col(label, fmt):
    if is_privacy_mode():
        return st.column_config.TextColumn(label)
    return st.column_config.NumberColumn(label, format=fmt)


# ================= 2. 弹窗逻辑 =================
@st.dialog("📝 操作中心")
def show_add_modal():
    privacy_mode = is_privacy_mode()
    tab1, tab2, tab3, tab4 = st.tabs(["股票交易", "期权交易", "💰 本金管理", "♻️ 回收站"])

    # --- 股票 ---
    with tab1:
        t_type = st.radio("交易方向", ["BUY", "SELL"], horizontal=True)
        is_sell = "SELL" in t_type
        current_holdings = db.get_portfolio_summary()
        valid_holdings = []
        if not current_holdings.empty:
            current_holdings['Quantity'] = pd.to_numeric(current_holdings['Quantity'], errors='coerce').fillna(0)
            valid_holdings = current_holdings[current_holdings['Quantity'] > 0.01]['Symbol'].tolist()

        with st.form("add_stock_form"):
            c1, c2 = st.columns(2)
            t_date = c1.date_input("日期", date.today())
            t_sym = ""
            if is_sell:
                if valid_holdings:
                    t_sym = c2.selectbox("选择持仓股票", valid_holdings)
                    holding_qty = 0
                    if t_sym:
                        val = current_holdings[current_holdings['Symbol'] == t_sym]['Quantity'].values
                        if len(val) > 0: holding_qty = val[0]
                    st.caption(f"💡 可卖持仓: {float(holding_qty):g} 股")
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
                    st.error("请选择要卖出的股票")
                elif is_sell and t_qty > holding_qty:
                    st.error(f"卖出数量超过持仓")
                else:
                    db.add_transaction(t_date, t_sym, final_type, t_qty, t_price, t_fee, t_note, asset_category='STOCK',
                                       multiplier=1)
                    st.cache_data.clear()
                    if 'portfolio_cache' in st.session_state: del st.session_state['portfolio_cache']
                    st.success("已保存")
                    st.rerun()

    # --- 期权 ---
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
                st.cache_data.clear()
                if 'portfolio_cache' in st.session_state: del st.session_state['portfolio_cache']
                st.success("期权交易已保存")
                st.rerun()

    # --- 本金管理 ---
    with tab3:
        curr_principal = db.get_total_invested()
        curr_cash = db.get_cash_balance()

        st.metric("当前总本金 (Principal)", fmt_money(curr_principal, 0), help="你的总投入（计算利润的基准）")
        st.metric("当前现金余额 (Cash)", fmt_money(curr_cash, 2), help="账户内可用现金")
        st.divider()

        mode = st.selectbox("操作类型", ["➕ 增加本金 (入金)", "➖ 减少本金 (出金)", "🔄 重置初始本金", "💸 单独校准现金"],
                            label_visibility="collapsed")

        # 1. 正常入金/出金
        if "增加" in mode or "减少" in mode:
            with st.form("flow_form"):
                f_date = st.date_input("日期", date.today())
                f_amount = st.number_input("金额", min_value=0.0, step=1000.0, format="%.2f")
                f_note = st.text_input("备注")
                if st.form_submit_button("提交", use_container_width=True):
                    type_code = 'DEPOSIT' if "增加" in mode else 'WITHDRAW'
                    db.manage_principal(f_date, type_code, f_amount, f_note)
                    st.cache_data.clear()
                    if 'portfolio_cache' in st.session_state: del st.session_state['portfolio_cache']
                    st.toast("✅ 资金已变动")
                    st.rerun()

        # 2. 重置本金
        elif "重置" in mode:
            with st.form("reset_form"):
                st.info("ℹ️ 此操作仅重置【计算利润的基准本金】，不会影响现金余额。")
                f_date = st.date_input("重置日期", date.today())
                reset_default = 0.0 if privacy_mode else float(curr_principal)
                f_amount = st.number_input("新本金总额", value=reset_default, step=1000.0)
                if st.form_submit_button("🔥 确认重置本金", use_container_width=True):
                    db.reset_principal_only(f_amount, f_date)
                    st.cache_data.clear()
                    if 'portfolio_cache' in st.session_state: del st.session_state['portfolio_cache']
                    st.toast("✅ 本金基准已重置")
                    st.rerun()

        # 3. 单独校准现金
        elif "校准现金" in mode:
            with st.form("fix_cash_form"):
                st.info("ℹ️ 如果发现现金对不上，可在此直接修改。")
                cash_default = 0.0 if privacy_mode else float(curr_cash)
                f_amount = st.number_input("实际现金余额", value=cash_default, step=100.0)
                if st.form_submit_button("校准现金", use_container_width=True):
                    db.set_cash_balance(f_amount)
                    st.cache_data.clear()
                    st.toast("✅ 现金已校准")
                    st.rerun()

        st.divider()
        st.caption("📜 最近资金变动")
        funds = db.get_fund_flows()
        if not funds.empty:
            display_f = funds.copy()
            display_f['display_type'] = display_f['type'].map(
                {'DEPOSIT': '🟢 入金', 'WITHDRAW': '🔴 出金', 'RESET': '🔄 重置'})
            if privacy_mode:
                display_f['amount'] = "****"
            edited = st.data_editor(
                display_f[['id', 'date', 'display_type', 'amount', 'note']],
                column_config={
                    "id": None,
                    "display_type": "类型",
                    "amount": money_col("金额", "$%.2f")
                },
                hide_index=True,
                key="fund_editor",
                num_rows="dynamic"
            )
            if st.session_state.get("fund_editor", {}).get("deleted_rows"):
                for idx in st.session_state["fund_editor"]["deleted_rows"]:
                    record_id = int(funds.iloc[idx]['id'])
                    db.delete_fund_flow(record_id)
                st.rerun()

    # --- 回收站 ---
    with tab4:
        deleted = db.get_deleted_transactions_last_7_days()
        if not deleted.empty:
            for idx, row in deleted.iterrows():
                c1, c2 = st.columns([4, 1])
                c1.text(f"{row['symbol']} {row['type']} {row['quantity']}")
                if c2.button("恢复", key=f"res_{row['id']}"):
                    db.restore_transaction(row['id'])
                    st.cache_data.clear()
                    st.rerun()
        else:
            st.caption("空")


# ================= 5. 主页面逻辑 =================

# 1. 大师语录
daily_quote = cf.get_random_quote()
st.markdown(f"""<div class="quote-card">“{daily_quote[0]}”<div class="quote-author">—— {daily_quote[1]}</div></div>""",
            unsafe_allow_html=True)

st.subheader("🔭 长期主义驾驶舱")

# --- 2. 宏观模块 ---
macro_data = ut.get_global_macro_data()
col_switch, col_privacy, _ = st.columns([1, 1, 3])
with col_switch:
    market_mode = st.radio("Market View", ["US", "CN"], horizontal=True, label_visibility="collapsed")
with col_privacy:
    st.toggle("隐私模式", key="privacy_mode", help="开启后隐藏所有金额")
privacy_mode = is_privacy_mode()

mc1, mc2 = st.columns(2)
if "US" in market_mode:
    vix, tnx = macro_data['vix'], macro_data['tnx']
    vix_str = f"{vix:.2f}" if vix else "N/A"
    vix_delta, vix_label = ("inverse", "贪婪 (风险)") if vix and vix < 15 else (
        ("normal", "恐慌 (机会)") if vix and vix > 30 else ("off", "市场情绪"))
    mc1.metric("🌊 VIX 恐慌指数 (US)", vix_str, vix_label, delta_color=vix_delta)
    mc2.metric("⚓ 10年美债收益率", f"{tnx:.2f}%" if tnx else "N/A", "全球资产锚", delta_color="off")
else:
    hsbfix, cnh = macro_data['hsbfix'], macro_data['cnh']
    hsbfix_str = f"{hsbfix:.2f}" if hsbfix else "N/A"
    hsbfix_delta, hsbfix_label = ("inverse", "贪婪 (风险)") if hsbfix and hsbfix < 15 else (
        ("normal", "恐慌 (黄金坑)") if hsbfix and hsbfix > 30 else ("off", "市场情绪"))
    mc1.metric("📉 恒指波幅 (hsbfix)", hsbfix_str, hsbfix_label, delta_color=hsbfix_delta)
    cnh_str = f"{cnh:.4f}" if cnh else "N/A"
    cnh_delta, cnh_label = ("inverse", "贬值 (压力)") if cnh and cnh > 7.25 else (
        ("normal", "升值 (流入)") if cnh and cnh < 6.9 else ("off", "汇率波动"))
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
    portfolio_df['Quantity'] = pd.to_numeric(portfolio_df['Quantity'], errors='coerce').fillna(0)
    portfolio_df = portfolio_df[portfolio_df['Quantity'] > 0.01]

    if 'last_update' not in st.session_state:
        portfolio_df = ut.update_portfolio_valuation(portfolio_df)
        st.session_state['portfolio_cache'] = portfolio_df
        st.session_state['last_update'] = datetime.now()
    else:
        cached_df = st.session_state['portfolio_cache']
        if len(cached_df) != len(portfolio_df):
            portfolio_df = ut.update_portfolio_valuation(portfolio_df)
            st.session_state['portfolio_cache'] = portfolio_df
        else:
            portfolio_df = cached_df

    market_val_usd = portfolio_df['Market Value'].sum()
    total_cost_usd = portfolio_df['Total Cost'].sum()

    if 'Days Held' in portfolio_df.columns and not portfolio_df['Days Held'].isnull().all():
        max_days_held = portfolio_df['Days Held'].max()
        highest_badge_icon, highest_badge_name = ut.get_badge_info(max_days_held)

st.markdown(
    f"""<div class="badge-container"><div class="badge-icon">{highest_badge_icon}</div><div class="badge-text">{highest_badge_name}<div class="badge-label">坚持 {int(max_days_held)} 天</div></div></div>""",
    unsafe_allow_html=True)

final_net_asset = market_val_usd + cash_balance
base = total_invested
pnl = final_net_asset - base
ret_pct = (pnl / base * 100) if base > 0 else 0.0

# 保存快照
db.save_daily_snapshot(date.today().strftime('%Y-%m-%d'), final_net_asset, base)

lev_ratio = (market_val_usd / final_net_asset) if final_net_asset > 0 else 999
cash_ratio = (cash_balance / final_net_asset * 100) if final_net_asset > 0 else 0
top3_conc = 0
if market_val_usd > 0:
    top3_conc = (portfolio_df.nlargest(3, 'Market Value')['Market Value'].sum() / market_val_usd) * 100

# 核心指标看板
with st.container():
    st.markdown('<div class="net-asset-card">', unsafe_allow_html=True)
    c_main = st.columns(1)[0]
    c_main.metric("💎 净资产 (Net Assets USD)", fmt_money(final_net_asset, 0), f"{ret_pct:+.2f}%")
    st.markdown('</div>', unsafe_allow_html=True)

st.write("")

c1, c2, c3, c4 = st.columns(4)
c1.metric("⚖️ 杠杆率", f"{lev_ratio:.2f}x", delta="安全" if lev_ratio <= 1.2 else "偏高",
          delta_color="inverse" if lev_ratio > 1.2 else "normal")

# 集中度告警（类似杠杆率的做法）
if top3_conc < 60:
    c2.metric("🎯 Top3 集中度", f"{top3_conc:.1f}%", delta="过低", delta_color="inverse")
elif top3_conc < 70:
    c2.metric("🎯 Top3 集中度", f"{top3_conc:.1f}%", delta="偏低", delta_color="inverse")
elif top3_conc < 80:
    c2.metric("🎯 Top3 集中度", f"{top3_conc:.1f}%", delta="接近阈值", delta_color="off")
else:
    c2.metric("🎯 Top3 集中度", f"{top3_conc:.1f}%", delta="良好 ✓", delta_color="normal")

c3.metric("🔫 现金/负债", fmt_money(abs(cash_balance), 0), f"{cash_ratio:+.1f}%")
c4.metric("🛡️ 总利润 (Profit)", fmt_money(pnl, 0), help="净资产 - 总投入本金")

st.divider()

# --- 4. 多维透视 (移到了中间) ---
if not portfolio_df.empty or abs(cash_balance) > 1:
    col_l, col_r = st.columns([1, 1.8])

    with col_l:
        st.caption("资产分布透视")
        pie_data = portfolio_df.copy()
        if cash_balance > 0:
            new_row = {'Symbol': 'CASH', 'Market Value': cash_balance}
            pie_data = pd.concat([pie_data, pd.DataFrame([new_row])], ignore_index=True)

        valid_pie = pie_data[pie_data['Market Value'] > 0.1]

        if not valid_pie.empty:
            ui.render_echarts_pie(valid_pie, 'Symbol', 'Market Value', key="chart_holdings", mask_value=privacy_mode)
        else:
            st.info("无数据")

    with col_r:
        st.caption("持仓明细 (自动折算 USD)")
        portfolio_df['PnL $'] = portfolio_df['Market Value'] - portfolio_df['Total Cost']
        portfolio_df['Safety Margin'] = portfolio_df.apply(
            lambda x: (x['Price'] - x['Avg Cost']) / x['Price'] * 100
            if x['Price'] > 0 and x['Type'] == 'STOCK' else 0, axis=1
        )

        portfolio_df['Badge'] = portfolio_df['Days Held'].apply(
            lambda d: ut.get_badge_info(d)[0] + " " + ut.get_badge_info(d)[1])

        display_df = portfolio_df.sort_values('Market Value', ascending=False)
        display_table = display_df.copy()
        if privacy_mode:
            for col in ['Avg Cost', 'Price', 'Market Value']:
                if col in display_table.columns:
                    display_table[col] = "****"

        st.dataframe(
            display_table,
            column_order=["Sector", "Symbol", "Quantity", "Avg Cost", "Price", "Market Value", "Safety Margin", "Badge",
                          "Days Held"],
            column_config={
                "Sector": st.column_config.TextColumn("赛道", width="small"),
                "Symbol": st.column_config.TextColumn("代码", width="small"),
                "Quantity": st.column_config.NumberColumn("持仓", format="%.0f"),
                "Avg Cost": money_col("成本", "%.2f"),
                "Price": money_col("现价", "%.2f"),
                "Market Value": money_col("市值", "$%.0f"),
                "Safety Margin": st.column_config.ProgressColumn("安全边际", format="%.1f%%", min_value=0,
                                                                 max_value=100),
                "Badge": st.column_config.TextColumn("荣誉", width="small"),
                "Days Held": st.column_config.NumberColumn("天数", format="%d")
            },
            use_container_width=True, height=450, hide_index=True
        )

st.divider()

# --- 5. 财富复利曲线 (极简版) ---
col_h1, col_h2 = st.columns([1, 4])
with col_h1:
    st.caption("📈 财富复利曲线")
with col_h2:
    # 极简切换：$ vs %
    chart_mode_sel = st.radio(
        "图表模式",
        ["$", "%"],
        horizontal=True,
        label_visibility="collapsed",
        key="chart_mode_toggle"
    )

# 映射逻辑
mode_key = 'value' if chart_mode_sel == '$' else 'pct'

# 获取数据并渲染
history_df = db.get_history_data()
# # 🔥🔥🔥 【诊断探针】开始 🔥🔥🔥
# st.write("🔍 诊断模式：查看底层数据")
# # 强制把 total_invested 转成数字看看到底是不是 0
# history_df['total_invested'] = pd.to_numeric(history_df['total_invested'], errors='coerce').fillna(0)
# # 计算一列临时的收益率看看
# history_df['debug_yield'] = (history_df['total_asset'] - history_df['total_invested']) / history_df['total_invested'] * 100
# st.dataframe(history_df, use_container_width=True)
# # 🔥🔥🔥 【诊断探针】结束 🔥🔥🔥

ui.render_history_chart(history_df, mode=mode_key, mask_value=privacy_mode)

st.divider()

# ================= 6. 交易流水 (持仓优先 + 市值排序) =================
st.subheader("📋 交易流水")

# 1. 获取所有交易
all_trans = db.get_all_transactions(False)

if not all_trans.empty:
    # 强制转换日期格式，避免 data_editor 报错
    all_trans['date'] = pd.to_datetime(all_trans['date'])

    # 2. 获取当前持仓信息 (修复点：优先读取带市值的缓存数据)
    # 之前报错是因为重新调用的 db.get_portfolio_summary() 只有成本没有市值
    if 'portfolio_cache' in st.session_state and not st.session_state['portfolio_cache'].empty:
        portfolio_df = st.session_state['portfolio_cache']
    else:
        # 如果缓存也没有（极少见），才去读原始数据库
        portfolio_df = db.get_portfolio_summary()

    # 提取持仓 symbol 及其市值，构建字典 {Symbol: MarketValue}
    active_holdings = {}
    if not portfolio_df.empty:
        # 防御性处理：确保 Quantity 列存在并转为数字
        if 'Quantity' in portfolio_df.columns:
            portfolio_df['Quantity'] = pd.to_numeric(portfolio_df['Quantity'], errors='coerce').fillna(0)

        # 🔥 修复核心：先检查 Market Value 列是否存在
        if 'Market Value' in portfolio_df.columns:
            portfolio_df['Market Value'] = pd.to_numeric(portfolio_df['Market Value'], errors='coerce').fillna(0)
        else:
            # 如果是原始数据没有市值，就填 0，保证不报错
            portfolio_df['Market Value'] = 0.0

        # 筛选出真正持有的 (数量 > 0)
        valid_p = portfolio_df[portfolio_df['Quantity'] > 0.01]
        if not valid_p.empty:
            active_holdings = dict(zip(valid_p['Symbol'], valid_p['Market Value']))

    # 3. 将交易记录拆分为 [持仓股] 和 [非持仓股]
    all_symbols = all_trans['symbol'].unique().tolist()

    active_symbols = [s for s in all_symbols if s in active_holdings]  # 当前持仓
    inactive_symbols = [s for s in all_symbols if s not in active_holdings]  # 已清仓

    # 4. 对持仓股按市值降序排序 (重仓在前)
    active_symbols.sort(key=lambda s: active_holdings.get(s, 0), reverse=True)

    # --- A. 渲染持仓股流水 (分个股折叠) ---
    for sym in active_symbols:
        df_sym = all_trans[all_trans['symbol'] == sym].sort_values('date', ascending=False)
        display_sym = df_sym.copy()
        count = len(df_sym)
        mv = active_holdings.get(sym, 0)
        if privacy_mode:
            display_sym['price'] = "****"
            mv_label = "****"
        else:
            mv_label = f"${mv:,.0f}"

        # 标题显示市值
        with st.expander(f"📦 {sym} (市值 {mv_label} · {count} 笔)"):
            edited = st.data_editor(
                display_sym[['id', 'date', 'type', 'quantity', 'price', 'note']],
                hide_index=True,
                use_container_width=True,
                key=f"editor_{sym}",
                num_rows="fixed",
                column_config={
                    "id": None,
                    "date": st.column_config.DateColumn("日期"),
                    "type": st.column_config.TextColumn("方向", width="small"),
                    "quantity": st.column_config.NumberColumn("数量"),
                    "price": money_col("价格", "$%.2f"),
                    "note": st.column_config.TextColumn("备注")
                }
            )
            # 删除逻辑
            if st.session_state.get(f"editor_{sym}", {}).get("deleted_rows"):
                for idx in st.session_state[f"editor_{sym}"]["deleted_rows"]:
                    db.soft_delete_transaction(int(df_sym.iloc[idx]['id']))
                st.cache_data.clear()
                if 'portfolio_cache' in st.session_state: del st.session_state['portfolio_cache']
                st.rerun()

    # --- B. 渲染非持仓/已清仓流水 (统一折叠) ---
    if inactive_symbols:
        df_inactive = all_trans[all_trans['symbol'].isin(inactive_symbols)].sort_values('date', ascending=False)
        display_inactive = df_inactive.copy()
        count_inactive = len(df_inactive)
        if privacy_mode:
            display_inactive['price'] = "****"

        with st.expander(f"🗄️ 其他 / 已清仓 ({count_inactive} 笔交易)"):
            edited_inactive = st.data_editor(
                display_inactive[['id', 'date', 'symbol', 'type', 'quantity', 'price', 'note']],
                hide_index=True,
                use_container_width=True,
                key="editor_inactive",
                num_rows="fixed",
                column_config={
                    "id": None,
                    "date": st.column_config.DateColumn("日期"),
                    "symbol": st.column_config.TextColumn("代码", width="small"),
                    "type": st.column_config.TextColumn("方向", width="small"),
                    "quantity": st.column_config.NumberColumn("数量"),
                    "price": money_col("价格", "$%.2f"),
                    "note": st.column_config.TextColumn("备注")
                }
            )
            # 删除逻辑
            if st.session_state.get("editor_inactive", {}).get("deleted_rows"):
                for idx in st.session_state["editor_inactive"]["deleted_rows"]:
                    db.soft_delete_transaction(int(df_inactive.iloc[idx]['id']))
                st.cache_data.clear()
                if 'portfolio_cache' in st.session_state: del st.session_state['portfolio_cache']
                st.rerun()

else:
    st.info("暂无交易记录，快去记一笔吧！")

# 底部悬浮按钮
st.markdown('<span id="fab-anchor"></span>', unsafe_allow_html=True)
if st.button("➕", key="fab_main"): show_add_modal()
