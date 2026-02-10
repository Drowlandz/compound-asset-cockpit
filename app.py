import streamlit as st
import pandas as pd
from datetime import date, datetime
import html
import data_manager as db
import config as cf
import utils as ut
import ui
from services import portfolio_service as pf_service
from services.snapshot_service import save_today_snapshot
from services import transaction_service as tx_service

# ================= 1. 初始化 =================
st.set_page_config(page_title="长期复利资产驾驶舱", layout="wide", page_icon="🔭")
db.init_db()
st.markdown(cf.CUSTOM_CSS, unsafe_allow_html=True)

def _parse_bool_flag(raw_value):
    if isinstance(raw_value, list):
        raw_value = raw_value[0] if raw_value else None
    if raw_value is None:
        return None
    text = str(raw_value).strip().lower()
    if text in ("1", "true", "yes", "on"):
        return True
    if text in ("0", "false", "no", "off"):
        return False
    return None


def _get_privacy_mode_from_query():
    try:
        return _parse_bool_flag(st.query_params.get("privacy"))
    except Exception:
        pass
    try:
        params = st.experimental_get_query_params()
        return _parse_bool_flag(params.get("privacy"))
    except Exception:
        return None


def _sync_privacy_mode_to_query(enabled):
    target = "1" if enabled else "0"
    try:
        current = str(st.query_params.get("privacy"))
        if current != target:
            st.query_params["privacy"] = target
        return
    except Exception:
        pass
    try:
        params = st.experimental_get_query_params()
        current = params.get("privacy", [None])[0]
        if current != target:
            params["privacy"] = [target]
            st.experimental_set_query_params(**params)
    except Exception:
        pass


query_privacy = _get_privacy_mode_from_query()
if 'privacy_mode' not in st.session_state:
    st.session_state['privacy_mode'] = bool(query_privacy) if query_privacy is not None else False

# 仅在 query 值发生变化时同步到 session，避免覆盖用户手动切换
last_query_privacy = st.session_state.get('_last_query_privacy')
if query_privacy is not None and query_privacy != last_query_privacy:
    st.session_state['privacy_mode'] = bool(query_privacy)
st.session_state['_last_query_privacy'] = query_privacy


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


def invalidate_portfolio_cache():
    st.session_state.pop('portfolio_cache', None)
    st.session_state.pop('last_update', None)


# ================= 2. 弹窗逻辑 =================
@st.dialog("📝 操作中心")
def show_add_modal():
    privacy_mode = is_privacy_mode()
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📈 股票", "📜 期权", "💰 资金", "♻️ 回收站", "📋 交易流水"])

    # --- 股票 ---
    with tab1:
        st.caption("记录股票买卖，提交后自动刷新持仓。")
        t_type = st.radio("交易方向", ["BUY", "SELL"], horizontal=True)
        is_sell = "SELL" in t_type
        current_holdings = db.get_stock_holdings_for_sell()
        valid_holdings = []
        selected_sell_symbol = ""
        holding_qty = 0.0
        if not current_holdings.empty:
            current_holdings['Quantity'] = pd.to_numeric(current_holdings['Quantity'], errors='coerce').fillna(0.0)
            valid_holdings = current_holdings[current_holdings['Quantity'] > 0.01]['Symbol'].astype(str).tolist()

        # 卖出时把选股放到 form 外，确保切换股票会即时刷新可卖数量
        if is_sell:
            c_sell, _ = st.columns([2, 2])
            if valid_holdings:
                selected_sell_symbol = c_sell.selectbox(
                    "选择持仓股票",
                    valid_holdings,
                    key="sell_symbol_picker"
                )
                matched = current_holdings[current_holdings['Symbol'] == selected_sell_symbol]
                if not matched.empty:
                    holding_qty = float(matched['Quantity'].iloc[0])
                if st.session_state.get("sell_qty_symbol") != selected_sell_symbol:
                    st.session_state["sell_qty_raw"] = f"{holding_qty:g}"
                    st.session_state["sell_qty_symbol"] = selected_sell_symbol
                c_sell.caption(f"💡 可卖持仓: {holding_qty:g} 股")
            else:
                c_sell.warning("无持仓可卖")
                st.session_state["sell_qty_raw"] = "0"
                st.session_state["sell_qty_symbol"] = ""

        with st.form("add_stock_form"):
            c1, c2 = st.columns(2)
            t_date = c1.date_input("日期", date.today())
            if is_sell:
                t_sym = selected_sell_symbol
                c2.text_input("卖出代码", value=t_sym if t_sym else "-", disabled=True)
            else:
                t_sym = c2.text_input("代码", "NVDA").upper()

            c3, c4 = st.columns(2)
            if is_sell:
                t_qty_raw = c3.text_input("数量 (股)", key="sell_qty_raw")
            else:
                t_qty_raw = c3.text_input("数量 (股)", value="100", key="buy_qty_raw")
            t_price_raw = c4.text_input("成交单价", value="0")
            c5, c6 = st.columns(2)
            t_fee_raw = c5.text_input("佣金", value="0")
            t_note = c6.text_input("笔记", placeholder="策略备注")

            if st.form_submit_button("提交交易", use_container_width=True, type="primary"):
                final_type = "SELL" if is_sell else "BUY"
                t_qty, err_qty = tx_service.parse_float_input(t_qty_raw, "数量 (股)", min_value=0.01)
                t_price, err_price = tx_service.parse_float_input(t_price_raw, "成交单价", min_value=0.0)
                t_fee, err_fee = tx_service.parse_float_input(t_fee_raw, "佣金", min_value=0.0)
                errors = [err for err in [err_qty, err_price, err_fee] if err]

                if errors:
                    st.error("；".join(errors))
                elif is_sell and not t_sym:
                    st.error("请选择要卖出的股票")
                elif is_sell and t_qty > holding_qty:
                    st.error(f"卖出数量超过持仓")
                else:
                    tx_service.add_stock_transaction(t_date, t_sym, final_type, t_qty, t_price, t_fee, t_note)
                    st.cache_data.clear()
                    invalidate_portfolio_cache()
                    st.success("已保存")
                    st.rerun()

    # --- 期权 ---
    with tab2:
        st.caption("记录期权开平仓，支持到期日/行权价/方向。")
        st.info("📌 期权无法自动查询实时价格；估值使用你手动维护的“当前价格（每股）”。")
        o_side = st.radio("方向", ["BUY", "SELL"], horizontal=True, key="option_side_toggle")
        is_option_sell = (o_side == "SELL")
        option_sell_positions = db.get_open_option_positions()
        selected_option_row = None
        option_holding_qty = 0.0

        if is_option_sell:
            if option_sell_positions.empty:
                st.warning("当前没有可卖出的期权持仓")
            else:
                option_rows = option_sell_positions.to_dict('records')
                option_labels = []
                option_map = {}
                for row in option_rows:
                    strike_txt = f"{float(row['strike']):g}" if pd.notna(row.get('strike')) else "-"
                    qty_txt = f"{float(row.get('quantity', 0)):g}"
                    label = f"{row['symbol']} {row['expiration']} {row['option_type']} {strike_txt} (可卖 {qty_txt} 张)"
                    option_labels.append(label)
                    option_map[label] = row

                selected_label = st.selectbox("选择期权持仓", option_labels, key="option_sell_picker")
                selected_option_row = option_map.get(selected_label)
                if selected_option_row is not None:
                    option_holding_qty = float(selected_option_row.get('quantity', 0.0))
                    if st.session_state.get("option_sell_qty_symbol") != selected_label:
                        st.session_state["option_sell_qty_raw"] = f"{option_holding_qty:g}"
                        st.session_state["option_sell_qty_symbol"] = selected_label
                    st.caption(f"💡 可卖持仓: {option_holding_qty:g} 张")

        with st.form("add_option_form"):
            c1, c2 = st.columns(2)
            o_date = c1.date_input("交易日期", date.today())
            c3, c4, c5 = st.columns(3)
            if is_option_sell and selected_option_row is not None:
                o_sym = str(selected_option_row['symbol']).upper()
                c2.text_input("正股代码", value=o_sym, disabled=True)

                exp_str = str(selected_option_row.get('expiration', ''))
                exp_ts = pd.to_datetime(exp_str, errors='coerce')
                exp_date = exp_ts.date() if pd.notna(exp_ts) else date.today()
                o_exp = c3.date_input("到期日", value=exp_date, disabled=True)

                o_strike = float(selected_option_row.get('strike', 0.0)) if pd.notna(selected_option_row.get('strike')) else 0.0
                c4.text_input("行权价", value=f"{o_strike:g}", disabled=True)

                o_type = str(selected_option_row.get('option_type', 'CALL')).upper()
                c5.text_input("类型", value=o_type, disabled=True)
            else:
                o_sym = c2.text_input("正股代码", "NVDA").upper()
                o_exp = c3.date_input("到期日")
                o_strike_raw = c4.text_input("行权价", value="0")
                o_type = c5.selectbox("类型", ["CALL", "PUT"])

            c6, c7 = st.columns(2)
            c6.text_input("方向", value=o_side, disabled=True)
            if is_option_sell:
                o_qty_raw = c7.text_input("张数", key="option_sell_qty_raw")
            else:
                o_qty_raw = c7.text_input("张数", value="1", key="option_buy_qty_raw")
            c8, c9 = st.columns(2)
            o_price_raw = c8.text_input("权利金", value="0")
            o_fee_raw = c9.text_input("佣金", value="0")
            if st.form_submit_button("提交期权交易", use_container_width=True, type="primary"):
                o_qty, err_qty = tx_service.parse_float_input(o_qty_raw, "张数", min_value=0.01)
                o_price, err_price = tx_service.parse_float_input(o_price_raw, "权利金", min_value=0.0)
                o_fee, err_fee = tx_service.parse_float_input(o_fee_raw, "佣金", min_value=0.0)
                errors = [err for err in [err_qty, err_price, err_fee] if err]

                if is_option_sell:
                    if selected_option_row is None:
                        errors.append("请选择要卖出的期权持仓")
                    elif o_qty > option_holding_qty:
                        errors.append("卖出张数超过可卖持仓")
                else:
                    o_strike, err_strike = tx_service.parse_float_input(o_strike_raw, "行权价", min_value=0.0)
                    if err_strike:
                        errors.append(err_strike)

                if errors:
                    st.error("；".join(errors))
                else:
                    tx_service.add_option_transaction(
                        o_date,
                        o_sym,
                        o_side,
                        o_qty,
                        o_price,
                        o_fee,
                        o_type,
                        o_strike,
                        o_exp,
                    )
                    st.cache_data.clear()
                    invalidate_portfolio_cache()
                    st.success("期权交易已保存")
                    st.rerun()

        st.divider()
        st.caption("期权当前价格维护（写入估值数据库）")
        option_positions = db.get_open_option_positions()
        if option_positions.empty:
            st.info("当前没有可维护价格的期权持仓。")
        else:
            option_rows = option_positions.to_dict('records')
            option_labels = []
            option_map = {}
            for row in option_rows:
                strike_txt = f"{float(row['strike']):g}" if pd.notna(row.get('strike')) else "-"
                qty_txt = f"{float(row.get('quantity', 0)):g}"
                label = f"{row['symbol']} {row['expiration']} {row['option_type']} {strike_txt} (持仓 {qty_txt} 张)"
                option_labels.append(label)
                option_map[label] = row

            with st.form("option_price_form"):
                selected_label = st.selectbox("选择期权合约", option_labels)
                selected = option_map[selected_label]
                existing_option_price = ut.get_stock_price_from_db(
                    selected['symbol'],
                    'OPTION',
                    {
                        'expiration': selected.get('expiration', ''),
                        'option_type': selected.get('option_type', ''),
                        'strike': selected.get('strike', '')
                    }
                )
                option_price_default = (
                    f"{float(existing_option_price):g}"
                    if existing_option_price is not None
                    else "0"
                )
                option_price_raw = st.text_input("当前价格（每股）", value=option_price_default)
                if existing_option_price is None:
                    st.warning("⚠️ 当前合约尚未设置价格，系统无法自动抓取实时期权价。")
                if st.form_submit_button("保存期权当前价格", use_container_width=True, type="primary"):
                    option_price, err_price = tx_service.parse_float_input(option_price_raw, "当前价格（每股）", min_value=0.0)
                    if err_price:
                        st.error(err_price)
                    else:
                        option_symbol_key = tx_service.save_option_price(selected, option_price)
                        st.cache_data.clear()
                        invalidate_portfolio_cache()
                        st.success(f"已写入：{option_symbol_key} = ${option_price:.2f}")
                        st.rerun()

    # --- 本金管理 ---
    with tab3:
        st.caption("入金/出金会影响本金与现金，重置本金仅影响利润基准。")
        curr_principal = db.get_total_invested()
        curr_cash = db.get_cash_balance()

        st.metric("当前总本金 (Principal)", fmt_money(curr_principal, 0), help="你的总投入（计算利润的基准）")
        st.metric("当前现金余额 (Cash)", fmt_money(curr_cash, 2), help="账户内可用现金")
        st.divider()

        mode = st.radio(
            "资金操作",
            ["➕ 入金", "➖ 出金", "🔄 重置本金", "💸 校准现金"],
            horizontal=True
        )

        # 1. 正常入金/出金
        if mode in ["➕ 入金", "➖ 出金"]:
            with st.form("flow_form"):
                f_date = st.date_input("日期", date.today())
                f_amount_raw = st.text_input("金额", value="0")
                f_note = st.text_input("备注")
                if st.form_submit_button("提交", use_container_width=True, type="primary"):
                    f_amount, err_amount = tx_service.parse_float_input(f_amount_raw, "金额", min_value=0.0)
                    if err_amount:
                        st.error(err_amount)
                    else:
                        tx_service.apply_fund_flow(f_date, mode, f_amount, f_note)
                        st.cache_data.clear()
                        invalidate_portfolio_cache()
                        st.toast("✅ 资金已变动")
                        st.rerun()

        # 2. 重置本金
        elif mode == "🔄 重置本金":
            with st.form("reset_form"):
                st.info("ℹ️ 此操作仅重置【计算利润的基准本金】，不会影响现金余额。")
                f_date = st.date_input("重置日期", date.today())
                reset_default = "0" if privacy_mode else f"{float(curr_principal):.2f}"
                f_amount_raw = st.text_input("新本金总额", value=reset_default)
                if st.form_submit_button("🔥 确认重置本金", use_container_width=True, type="primary"):
                    f_amount, err_amount = tx_service.parse_float_input(f_amount_raw, "新本金总额")
                    if err_amount:
                        st.error(err_amount)
                    else:
                        tx_service.reset_principal(f_date, f_amount)
                        st.cache_data.clear()
                        invalidate_portfolio_cache()
                        st.toast("✅ 本金基准已重置")
                        st.rerun()

        # 3. 单独校准现金
        elif mode == "💸 校准现金":
            with st.form("fix_cash_form"):
                st.info("ℹ️ 如果发现现金对不上，可在此直接修改。")
                cash_default = "0" if privacy_mode else f"{float(curr_cash):.2f}"
                f_amount_raw = st.text_input("实际现金余额", value=cash_default)
                if st.form_submit_button("校准现金", use_container_width=True, type="primary"):
                    f_amount, err_amount = tx_service.parse_float_input(f_amount_raw, "实际现金余额")
                    if err_amount:
                        st.error(err_amount)
                    else:
                        tx_service.calibrate_cash(f_amount)
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
                    tx_service.delete_fund_flow(record_id)
                st.rerun()

    # --- 回收站 ---
    with tab4:
        st.caption("可恢复近 7 天误删交易。")
        deleted = db.get_deleted_transactions_last_7_days()
        if not deleted.empty:
            for idx, row in deleted.iterrows():
                c1, c2 = st.columns([4, 1])
                c1.text(f"{row['symbol']} {row['type']} {row['quantity']}")
                if c2.button("恢复", key=f"res_{row['id']}", type="secondary", use_container_width=True):
                    tx_service.restore_transaction(int(row['id']))
                    st.cache_data.clear()
                    st.rerun()
        else:
            st.caption("空")

    # --- 交易流水 ---
    with tab5:
        st.caption("查看并管理交易记录。")
        render_transaction_flow(privacy_mode, show_title=False)


def render_transaction_flow(privacy_mode, show_title=True):
    if show_title:
        st.subheader("📋 交易流水")

    all_trans = db.get_all_transactions(False)
    if not all_trans.empty:
        all_trans['date'] = pd.to_datetime(all_trans['date'])

        if 'portfolio_cache' in st.session_state and not st.session_state['portfolio_cache'].empty:
            portfolio_df_local = st.session_state['portfolio_cache']
        else:
            portfolio_df_local = db.get_portfolio_summary()

        active_holdings = {}
        if not portfolio_df_local.empty:
            if 'Quantity' in portfolio_df_local.columns:
                portfolio_df_local['Quantity'] = pd.to_numeric(portfolio_df_local['Quantity'], errors='coerce').fillna(0)
            if 'Market Value' in portfolio_df_local.columns:
                portfolio_df_local['Market Value'] = pd.to_numeric(
                    portfolio_df_local['Market Value'], errors='coerce'
                ).fillna(0)
            else:
                portfolio_df_local['Market Value'] = 0.0

            valid_p = portfolio_df_local[portfolio_df_local['Quantity'] > 0.01]
            if not valid_p.empty:
                active_holdings = dict(zip(valid_p['Symbol'], valid_p['Market Value']))

        all_symbols = all_trans['symbol'].unique().tolist()
        active_symbols = [s for s in all_symbols if s in active_holdings]
        inactive_symbols = [s for s in all_symbols if s not in active_holdings]
        active_symbols.sort(key=lambda s: active_holdings.get(s, 0), reverse=True)

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

            with st.expander(f"📦 {sym} (市值 {mv_label} · {count} 笔)"):
                st.data_editor(
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
                if st.session_state.get(f"editor_{sym}", {}).get("deleted_rows"):
                    for idx in st.session_state[f"editor_{sym}"]["deleted_rows"]:
                        tx_service.soft_delete_transaction(int(df_sym.iloc[idx]['id']))
                    st.cache_data.clear()
                    invalidate_portfolio_cache()
                    st.rerun()

        if inactive_symbols:
            df_inactive = all_trans[all_trans['symbol'].isin(inactive_symbols)].sort_values('date', ascending=False)
            display_inactive = df_inactive.copy()
            count_inactive = len(df_inactive)
            if privacy_mode:
                display_inactive['price'] = "****"

            with st.expander(f"🗄️ 其他 / 已清仓 ({count_inactive} 笔交易)"):
                st.data_editor(
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
                if st.session_state.get("editor_inactive", {}).get("deleted_rows"):
                    for idx in st.session_state["editor_inactive"]["deleted_rows"]:
                        tx_service.soft_delete_transaction(int(df_inactive.iloc[idx]['id']))
                    st.cache_data.clear()
                    invalidate_portfolio_cache()
                    st.rerun()
    else:
        st.info("暂无交易记录，快去记一笔吧！")


# ================= 5. 主页面逻辑 =================

# 1. 大师语录
daily_quote = cf.get_random_quote()
st.markdown(f"""<div class="quote-card">“{daily_quote[0]}”<div class="quote-author">—— {daily_quote[1]}</div></div>""",
            unsafe_allow_html=True)

st.subheader("🔭 长期复利资产驾驶舱")

# --- 2. 宏观模块 ---
macro_data = ut.get_global_macro_data()
col_switch, col_privacy, _ = st.columns([1, 1, 3])
with col_switch:
    market_mode = st.radio("Market View", ["US", "CN"], horizontal=True, label_visibility="collapsed")
with col_privacy:
    st.toggle("隐私模式", key="privacy_mode", help="开启后隐藏所有金额")
privacy_mode = is_privacy_mode()
_sync_privacy_mode_to_query(privacy_mode)

if privacy_mode:
    st.markdown(
        """
        <style>
        .privacy-fab-left {
            position: fixed;
            left: 14px;
            top: 50%;
            transform: translateY(-50%);
            z-index: 9998;
        }
        .privacy-fab-left form {
            margin: 0;
        }
        .privacy-fab-left button {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            writing-mode: vertical-rl;
            text-orientation: mixed;
            gap: 6px;
            min-height: 132px;
            padding: 12px 10px;
            border-radius: 12px;
            border: 1px solid #fda4af;
            background: linear-gradient(180deg, #ffe4e6 0%, #fecdd3 100%);
            color: #9f1239;
            font-weight: 700;
            font-size: 12px;
            letter-spacing: 0.4px;
            text-decoration: none;
            box-shadow: 0 8px 20px rgba(190, 24, 93, 0.22);
            transition: transform 0.15s ease, box-shadow 0.15s ease, background 0.15s ease;
            cursor: pointer;
        }
        .privacy-fab-left button:hover {
            transform: translateY(-2px);
            box-shadow: 0 12px 24px rgba(190, 24, 93, 0.28);
            background: linear-gradient(180deg, #fecdd3 0%, #fda4af 100%);
        }
        @media (max-width: 768px) {
            .privacy-fab-left {
                left: 8px;
                top: auto;
                bottom: 100px;
                transform: none;
            }
            .privacy-fab-left button {
                writing-mode: horizontal-tb;
                min-height: auto;
                padding: 8px 10px;
                border-radius: 10px;
            }
        }
        </style>
        <div class="privacy-fab-left">
            <form method="get" action="">
                <input type="hidden" name="privacy" value="0" />
                <button type="submit" title="点击关闭隐私模式">🙈 隐私中</button>
            </form>
        </div>
        """,
        unsafe_allow_html=True
    )

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

market_val_usd = 0.0
total_cost_usd = 0.0
max_days_held = 0.0
highest_badge_icon = "🌱"
highest_badge_name = "新手"

if not portfolio_df.empty:
    portfolio_df = pf_service.filter_active_positions(portfolio_df)

    has_cache = (
        'last_update' in st.session_state
        and 'portfolio_cache' in st.session_state
    )
    if not has_cache:
        portfolio_df = ut.update_portfolio_valuation(portfolio_df)
        st.session_state['portfolio_cache'] = portfolio_df
        st.session_state['last_update'] = datetime.now()
    else:
        cached_df = st.session_state.get('portfolio_cache')
        if cached_df is None:
            portfolio_df = ut.update_portfolio_valuation(portfolio_df)
            st.session_state['portfolio_cache'] = portfolio_df
            st.session_state['last_update'] = datetime.now()
        elif len(cached_df) != len(portfolio_df):
            portfolio_df = ut.update_portfolio_valuation(portfolio_df)
            st.session_state['portfolio_cache'] = portfolio_df
            st.session_state['last_update'] = datetime.now()
        else:
            portfolio_df = cached_df

    max_days_held, highest_badge_icon, highest_badge_name = pf_service.get_highest_badge(
        portfolio_df,
        ut.get_badge_info
    )

st.markdown(
    f"""<div class="badge-container"><div class="badge-icon">{highest_badge_icon}</div><div class="badge-text">{highest_badge_name}<div class="badge-label">坚持 {int(max_days_held)} 天</div></div></div>""",
    unsafe_allow_html=True)

metrics = pf_service.calculate_account_metrics(
    portfolio_df=portfolio_df,
    cash_balance=cash_balance,
    total_invested=total_invested
)
market_val_usd = metrics['market_val_usd']
total_cost_usd = metrics['total_cost_usd']
final_net_asset = metrics['final_net_asset']
base = metrics['base']
pnl = metrics['pnl']
ret_pct = metrics['ret_pct']
holding_ratio_pct = metrics['holding_ratio_pct']
lev_ratio = metrics['lev_ratio']
cash_ratio = metrics['cash_ratio']
top3_conc = metrics['top3_conc']

# 保存快照
save_today_snapshot(final_net_asset, base)

# 核心指标看板
with st.container():
    c_net, c_hold = st.columns([1.25, 1.0])
    with c_net:
        st.markdown('<div class="net-asset-card">', unsafe_allow_html=True)
        st.metric("💎 净资产 (Net Assets USD)", fmt_money(final_net_asset, 0), f"{ret_pct:+.2f}%")
        st.markdown('</div>', unsafe_allow_html=True)
    with c_hold:
        st.markdown('<div class="holding-asset-card">', unsafe_allow_html=True)
        if is_privacy_mode():
            hold_delta = "占净资产 ****"
        else:
            ratio_text = f"{holding_ratio_pct:.1f}%" if abs(final_net_asset) > 1e-9 else "N/A"
            hold_delta = f"占净资产 {ratio_text}"
        st.metric("📦 持仓市值 (USD)", fmt_money(market_val_usd, 0), hold_delta, delta_color="off")
        st.markdown('</div>', unsafe_allow_html=True)

st.write("")

c1, c2, c3, c4 = st.columns(4)
lev_delta, lev_color = pf_service.leverage_status(lev_ratio)
c1.metric("⚖️ 杠杆率", f"{lev_ratio:.2f}x", delta=lev_delta, delta_color=lev_color)

# 集中度告警（类似杠杆率的做法）
conc_delta, conc_color = pf_service.concentration_status(top3_conc)
c2.metric("🎯 Top3 集中度", f"{top3_conc:.1f}%", delta=conc_delta, delta_color=conc_color)

c3.metric("🔫 现金/负债", fmt_money(abs(cash_balance), 0), f"{cash_ratio:+.1f}%")
c4.metric("🛡️ 总利润 (Profit)", fmt_money(pnl, 0), help="净资产 - 总投入本金")

st.divider()

# --- 4. 多维透视 (移到了中间) ---
if not portfolio_df.empty or abs(cash_balance) > 1:
    col_l, col_r = st.columns([1, 1.8])

    with col_l:
        st.caption("资产分布透视")
        perspective_mode = st.radio(
            "透视视图",
            ["持仓", "赛道"],
            horizontal=True,
            label_visibility="collapsed",
            key="asset_perspective_mode"
        )

        pie_data = pd.DataFrame()
        name_col = "Symbol"
        pie_palette = None
        if perspective_mode == "持仓":
            # 持仓恢复默认配色
            pie_data = portfolio_df.copy()
            if cash_balance > 0:
                new_row = {'Symbol': 'CASH', 'Market Value': cash_balance}
                pie_data = pd.concat([pie_data, pd.DataFrame([new_row])], ignore_index=True)
            name_col = "Symbol"
        else:
            # 赛道使用中饱和离散配色（保留区分度，降低刺眼感）
            pie_palette = [
                "#D95D83", "#4FA8C8", "#D7B55B", "#7C6CB0", "#4FAFA4",
                "#D07A4F", "#8F6FC3", "#5C8FD8", "#4FAF8F", "#D86D8C",
                "#4D8FA8", "#D8B86A", "#89AF5A", "#B85D5D", "#7A6A96",
                "#58A0B8", "#C66FA6", "#D39A6D", "#5E9F8E", "#6F8193"
            ]
            sector_df = portfolio_df.copy()
            if 'Sector' not in sector_df.columns:
                sector_df['Sector'] = 'N/A'
            sector_df['Sector'] = sector_df['Sector'].fillna('N/A')
            pie_data = sector_df.groupby('Sector', as_index=False)['Market Value'].sum()
            pie_data.rename(columns={'Sector': 'Category'}, inplace=True)
            if cash_balance > 0:
                cash_row = pd.DataFrame([{'Category': '💵 现金', 'Market Value': cash_balance}])
                pie_data = pd.concat([pie_data, cash_row], ignore_index=True)
            name_col = "Category"

        valid_pie = pie_data[pie_data['Market Value'] > 0.1]

        if not valid_pie.empty:
            ui.render_echarts_pie(
                valid_pie,
                name_col,
                'Market Value',
                key=f"chart_distribution_{perspective_mode}",
                mask_value=privacy_mode,
                color_palette=pie_palette
            )
        else:
            st.info("无数据")

    with col_r:
        st.caption("持仓明细 (自动折算 USD)")
        display_df = pf_service.build_holdings_display_df(portfolio_df, ut.get_badge_info)
        display_table = display_df[
            ["Sector", "Symbol", "Quantity", "Avg Cost", "Price", "Market Value", "Safety Margin", "Badge", "Days Held"]
        ].copy()

        column_defs = [
            {"key": "Sector", "label": "赛道", "width": 108, "sensitive": False},
            {"key": "Symbol", "label": "代码", "width": 96, "sensitive": False},
            {"key": "Quantity", "label": "数量", "width": 82, "sensitive": True},
            {"key": "Avg Cost", "label": "买入价", "width": 98, "sensitive": False},
            {"key": "Price", "label": "现价", "width": 96, "sensitive": False},
            {"key": "Market Value", "label": "市值", "width": 112, "sensitive": True},
            {"key": "Safety Margin", "label": "安全边际", "width": 220, "sensitive": False},
            {"key": "Badge", "label": "荣誉", "width": 148, "sensitive": False},
            {"key": "Days Held", "label": "天数", "width": 74, "sensitive": False},
        ]
        visible_columns = [col for col in column_defs if not (privacy_mode and col["sensitive"])]

        def fmt_int(value):
            try:
                return f"{float(value):.0f}"
            except (TypeError, ValueError):
                return ""

        def fmt_money(value, decimals):
            try:
                return f"${float(value):,.{decimals}f}"
            except (TypeError, ValueError):
                return ""

        colgroup_html = "<colgroup>" + "".join(
            [f"<col style='width:{col['width']}px;'>" for col in visible_columns]
        ) + "</colgroup>"
        headers_html = "".join(
            ["<th>{}</th>".format(html.escape(col["label"])) for col in visible_columns]
        )
        table_min_width = max(sum(col["width"] for col in visible_columns), 680)

        table_rows = []
        for _, row in display_table.iterrows():
            cells = []
            for col in visible_columns:
                key = col["key"]
                if key == "Safety Margin":
                    try:
                        safety_float = float(row.get("Safety Margin", 0) or 0)
                    except (TypeError, ValueError):
                        safety_float = 0.0
                    bar_width = max(0.0, min(abs(safety_float), 100.0))
                    sign_cls = "sm-pos" if safety_float > 0 else "sm-neg" if safety_float < 0 else "sm-zero"
                    safety_label = f"{safety_float:+.1f}%"
                    cells.append(
                        "<td>"
                        "<div class='sm-wrap'>"
                        "<div class='sm-track'>"
                        f"<div class='sm-fill {sign_cls}' style='width:{bar_width:.1f}%;'></div>"
                        "</div>"
                        f"<span class='sm-label {sign_cls}'>{safety_label}</span>"
                        "</div>"
                        "</td>"
                    )
                elif key in ("Quantity", "Days Held"):
                    cells.append(f"<td>{fmt_int(row.get(key, ''))}</td>")
                elif key in ("Avg Cost", "Price"):
                    cells.append(f"<td>{fmt_money(row.get(key, ''), 2)}</td>")
                elif key == "Market Value":
                    cells.append(f"<td>{fmt_money(row.get(key, ''), 0)}</td>")
                else:
                    cells.append(f"<td>{html.escape(str(row.get(key, '')))}</td>")

            table_rows.append("<tr>" + "".join(cells) + "</tr>")

        st.markdown(
            """
            <style>
            .holdings-wrap { max-height: 450px; overflow: auto; border: 1px solid #e2e8f0; border-radius: 12px; background: #ffffff; }
            .holdings-table { width: 100%; border-collapse: collapse; font-size: 13px; }
            .holdings-table thead th {
                position: sticky; top: 0; z-index: 1;
                background: #f8fafc; color: #334155; font-weight: 700;
                text-align: left; padding: 10px 10px; border-bottom: 1px solid #e2e8f0;
            }
            .holdings-table tbody td {
                padding: 9px 10px; border-bottom: 1px solid #f1f5f9; color: #0f172a; white-space: nowrap;
            }
            .holdings-table tbody tr:hover { background: #f8fafc; }
            .sm-wrap { display: flex; align-items: center; gap: 8px; width: 100%; }
            .sm-track {
                flex: 1 1 auto; min-width: 120px; height: 8px; border-radius: 999px; overflow: hidden;
                background: #e2e8f0; border: 1px solid #cbd5e1;
            }
            .sm-fill { height: 100%; border-radius: 999px; filter: saturate(0.72); }
            .sm-fill.sm-pos { background: linear-gradient(90deg, rgba(34, 197, 94, 0.82), rgba(22, 163, 74, 0.82)); }
            .sm-fill.sm-neg { background: linear-gradient(90deg, rgba(248, 113, 113, 0.82), rgba(220, 38, 38, 0.82)); }
            .sm-fill.sm-zero { background: rgba(148, 163, 184, 0.9); }
            .sm-label { font-weight: 400; font-size: 13px; min-width: 56px; text-align: right; }
            .sm-label.sm-pos { color: rgba(22, 163, 74, 0.86); }
            .sm-label.sm-neg { color: rgba(220, 38, 38, 0.86); }
            .sm-label.sm-zero { color: #64748b; }
            </style>
            """,
            unsafe_allow_html=True
        )
        st.markdown(
            "<div class='holdings-wrap'>"
            f"<table class='holdings-table' style='min-width:{table_min_width}px;'>"
            f"{colgroup_html}"
            "<thead><tr>"
            f"{headers_html}"
            "</tr></thead>"
            f"<tbody>{''.join(table_rows)}</tbody>"
            "</table>"
            "</div>",
            unsafe_allow_html=True
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

# --- 6. 收益日历 ---
st.subheader("🗓️ 收益日历")
if st.session_state.get("pnl_calendar_view") not in [None, "月", "年"]:
    st.session_state["pnl_calendar_view"] = "月"
if "pnl_calendar_metric" not in st.session_state:
    st.session_state["pnl_calendar_metric"] = "%"
elif st.session_state.get("pnl_calendar_metric") not in ["$", "%"]:
    st.session_state["pnl_calendar_metric"] = "%"

cal_left, cal_right = st.columns([1.0, 2.6], gap="medium")
with cal_right:
    cal_c1, cal_c2, cal_c3, cal_c4 = st.columns([1.2, 1.2, 1.0, 1.0])
    with cal_c1:
        cal_view = st.radio(
            "日历视图",
            ["月", "年"],
            horizontal=True,
            label_visibility="collapsed",
            key="pnl_calendar_view"
        )
    with cal_c2:
        cal_metric = st.radio(
            "收益维度",
            ["$", "%"],
            horizontal=True,
            label_visibility="collapsed",
            key="pnl_calendar_metric"
        )

    years, default_year, default_month = ui.get_pnl_calendar_options(history_df)
    year_idx = years.index(default_year) if default_year in years else len(years) - 1
    with cal_c3:
        selected_year = st.selectbox(
            "年份",
            years,
            index=max(year_idx, 0),
            key="pnl_calendar_year",
            label_visibility="collapsed"
        )

    selected_month = default_month
    month_idx = max(min(default_month - 1, 11), 0)
    with cal_c4:
        selected_month = st.selectbox(
            "月份",
            list(range(1, 13)),
            index=month_idx,
            format_func=lambda x: f"{x}月",
            key="pnl_calendar_month",
            label_visibility="collapsed",
            disabled=(cal_view != "月")
        )

    ui.render_pnl_calendar(
        history_df=history_df,
        view_mode='month' if cal_view == "月" else 'year',
        metric_mode='amount' if cal_metric == "$" else 'rate',
        year=selected_year,
        month=selected_month if cal_view == "月" else None,
        mask_value=privacy_mode
    )

with cal_left:
    period_stats = ui.get_pnl_period_stats(history_df)
    anchor_date = period_stats["anchor_date"]
    # 与右侧筛选控件行做高度对齐，卡片从日历主体同一水平线开始
    st.markdown('<div style="height:46px;"></div>', unsafe_allow_html=True)
    st.markdown(
        """
        <style>
        .pnl-side-card {
            width: 100%;
            margin-bottom: 6px;
            border-radius: 10px;
            padding: 8px 10px;
            min-height: 64px;
            display: flex;
            flex-direction: column;
            justify-content: center;
            transition: transform 0.16s ease, box-shadow 0.16s ease, filter 0.16s ease;
        }
        .pnl-side-card:hover {
            transform: translateY(-2px) scale(1.01);
            box-shadow: 0 10px 20px rgba(15, 23, 42, 0.16);
            filter: saturate(1.04);
        }
        .pnl-side-title {
            font-size: 11px;
            color: #334155;
            font-weight: 700;
            line-height: 1.2;
        }
        .pnl-side-value {
            margin-top: 5px;
            font-size: 17px;
            font-weight: 400;
            line-height: 1.1;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    def _period_card_style(val):
        if val > 0:
            return ("linear-gradient(135deg, #ecfdf5 0%, #bbf7d0 100%)", "#22c55e", "#166534")
        if val < 0:
            return ("linear-gradient(135deg, #fef2f2 0%, #fecaca 100%)", "#ef4444", "#991b1b")
        return ("linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%)", "#94a3b8", "#334155")

    def _period_text(val, metric_mode):
        if metric_mode == "$":
            if privacy_mode:
                return "****"
            return f"${val:+,.0f}"
        return f"{val:+.2f}%"

    card_items = [
        ("本周收益", period_stats["week"]),
        ("本月收益", period_stats["month"]),
        ("今年收益", period_stats["year"]),
    ]

    for title, data in card_items:
        card_val = data["amount"] if cal_metric == "$" else data["rate"]
        bg, border, text_color = _period_card_style(card_val)
        value_text = _period_text(card_val, cal_metric)
        st.markdown(
            f"""
            <div class="pnl-side-card" style="border:1px solid {border}; background:{bg};">
                <div class="pnl-side-title">{title}</div>
                <div class="pnl-side-value" style="color:{text_color};">{value_text}</div>
            </div>
            """,
            unsafe_allow_html=True
        )
    st.caption(f"统计截止：{anchor_date:%Y-%m-%d}")

# 底部悬浮按钮
st.markdown('<span id="fab-anchor"></span>', unsafe_allow_html=True)
if st.button("➕", key="fab_main"): show_add_modal()
