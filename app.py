# app.py
import streamlit as st
import pandas as pd
from datetime import date, datetime
import data_manager as db
import config as cf  # 导入配置
import utils as ut  # 导入逻辑
import ui  # 导入图表

# ================= 1. 初始化 =================
st.set_page_config(page_title="长期主义资产管理", layout="wide", page_icon="🔭")
db.init_db()
st.markdown(cf.CUSTOM_CSS, unsafe_allow_html=True)  # 加载 CSS


# ================= 2. 弹窗逻辑 (操作中心) =================
@st.dialog("📝 操作中心")
def show_add_modal():
    tab1, tab2, tab3, tab4 = st.tabs(["股票交易", "期权交易", "资金进出", "♻️ 回收站"])

    # --- 股票 ---
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
                st.success("期权交易已保存")
                st.rerun()

    # --- 资金 ---
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

    # --- 回收站 ---
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
daily_quote = cf.get_random_quote()
st.markdown(f"""<div class="quote-card">“{daily_quote[0]}”<div class="quote-author">—— {daily_quote[1]}</div></div>""",
            unsafe_allow_html=True)

st.subheader("🔭 长期主义驾驶舱")

# --- 2. 宏观模块 (UI魔改版) ---
macro_data = ut.get_global_macro_data()

# 开关按钮
col_switch, _ = st.columns([1, 4])
with col_switch:
    market_mode = st.radio("Market View", ["🇺🇸 美股气候", "🇨🇳 中国资产"], horizontal=True, label_visibility="collapsed")

mc1, mc2 = st.columns(2)

if "美股" in market_mode:
    vix, tnx = macro_data['vix'], macro_data['tnx']
    vix_str = f"{vix:.2f}" if vix else "N/A"
    vix_delta, vix_label = ("inverse", "贪婪 (风险)") if vix and vix < 15 else (
        ("normal", "恐慌 (机会)") if vix and vix > 30 else ("off", "市场情绪"))
    mc1.metric("🌊 VIX 恐慌指数 (US)", vix_str, vix_label, delta_color=vix_delta)
    mc2.metric("⚓ 10年美债收益率", f"{tnx:.2f}%" if tnx else "N/A", "全球资产锚", delta_color="off")
else:
    vhsi, cnh = macro_data['vhsi'], macro_data['cnh']
    vhsi_str = f"{vhsi:.2f}" if vhsi else "N/A"
    vhsi_delta, vhsi_label = ("inverse", "贪婪 (风险)") if vhsi and vhsi < 15 else (
        ("normal", "恐慌 (黄金坑)") if vhsi and vhsi > 30 else ("off", "市场情绪"))
    mc1.metric("📉 恒指波幅 (VHSI)", vhsi_str, vhsi_label, delta_color=vhsi_delta)
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
    if 'last_update' not in st.session_state:
        portfolio_df = ut.update_portfolio_valuation(portfolio_df)
        st.session_state['portfolio_cache'] = portfolio_df
        st.session_state['last_update'] = datetime.now()
    else:
        portfolio_df = st.session_state['portfolio_cache']

    market_val_usd = portfolio_df['Market Value'].sum()
    total_cost_usd = portfolio_df['Total Cost'].sum()

    if 'Days Held' in portfolio_df.columns and not portfolio_df['Days Held'].isnull().all():
        max_days_held = portfolio_df['Days Held'].max()
        highest_badge_icon, highest_badge_name = ut.get_badge_info(max_days_held)

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
ui.render_history_chart(history_df)

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
                ui.render_echarts_pie(valid_pie, 'Symbol', 'Market Value')
            else:
                st.info("无数据")
        with chart_tab2:
            if not valid_pie.empty:
                sec_df = valid_pie.groupby('Sector')['Market Value'].sum().reset_index()
                ui.render_echarts_pie(sec_df, 'Sector', 'Market Value')
            else:
                st.info("无数据")
        with chart_tab3:
            if not valid_pie.empty:
                curr_df = valid_pie.groupby('Currency')['Market Value'].sum().reset_index()
                ui.render_echarts_pie(curr_df, 'Currency', 'Market Value')
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
            lambda d: ut.get_badge_info(d)[0] + " " + ut.get_badge_info(d)[1])

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