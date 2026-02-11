import streamlit as st
import pandas as pd
from datetime import date, datetime
from pathlib import Path
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


def _get_query_flag(flag_name):
    try:
        return _parse_bool_flag(st.query_params.get(flag_name))
    except Exception:
        pass
    try:
        params = st.experimental_get_query_params()
        return _parse_bool_flag(params.get(flag_name))
    except Exception:
        return None


def _get_privacy_mode_from_query():
    return _get_query_flag("privacy")


def _get_dark_mode_from_query():
    return _get_query_flag("dark")


def _sync_modes_to_query(privacy_enabled, dark_enabled):
    target_privacy = "1" if privacy_enabled else "0"
    target_dark = "1" if dark_enabled else "0"

    # 优先一次性写入，避免两个开关分别写 query 导致切换抖动
    try:
        params = st.experimental_get_query_params()
        current_privacy = _parse_bool_flag(params.get("privacy"))
        current_dark = _parse_bool_flag(params.get("dark"))
        if current_privacy == bool(privacy_enabled) and current_dark == bool(dark_enabled):
            return
        params["privacy"] = [target_privacy]
        params["dark"] = [target_dark]
        st.experimental_set_query_params(**params)
        return
    except Exception:
        pass
    try:
        current_privacy = _parse_bool_flag(st.query_params.get("privacy"))
        current_dark = _parse_bool_flag(st.query_params.get("dark"))
        if current_privacy != bool(privacy_enabled):
            st.query_params["privacy"] = target_privacy
        if current_dark != bool(dark_enabled):
            st.query_params["dark"] = target_dark
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

query_dark = _get_dark_mode_from_query()
if 'dark_mode' not in st.session_state:
    st.session_state['dark_mode'] = bool(query_dark) if query_dark is not None else False

last_query_dark = st.session_state.get('_last_query_dark')
if query_dark is not None and query_dark != last_query_dark:
    st.session_state['dark_mode'] = bool(query_dark)
st.session_state['_last_query_dark'] = query_dark


def is_privacy_mode():
    return bool(st.session_state.get('privacy_mode', False))


def is_dark_mode():
    return bool(st.session_state.get('dark_mode', False))


def render_runtime_theme_css():
    if not is_dark_mode():
        return
    st.markdown(
        """
        <style>
        .stApp {
            background: radial-gradient(circle at 12% 10%, #1f2937 0%, #0b0f14 40%, #05080d 100%);
            color: #e5e7eb;
        }
        .main .block-container {
            background: transparent;
        }
        h1, h2, h3, h4, h5, h6, p, span, label {
            color: #e5e7eb;
        }
        .quote-card {
            background: linear-gradient(120deg, #111827 0%, #0f172a 100%);
            border-left-color: #38bdf8;
            color: #e2e8f0;
            box-shadow: 0 10px 24px rgba(2, 6, 23, 0.45);
        }
        .quote-author {
            color: #94a3b8;
        }
        .badge-container {
            background: rgba(15, 23, 42, 0.92);
            border-color: #facc15;
            box-shadow: 0 10px 25px rgba(2, 6, 23, 0.55);
        }
        div[data-testid="stMetric"] {
            background: linear-gradient(130deg, #111827 0%, #0f172a 100%);
            border-color: #334155;
            box-shadow: 0 10px 24px rgba(2, 6, 23, 0.4);
        }
        div[data-testid="stMetric"] label {
            color: #94a3b8 !important;
        }
        div[data-testid="stMetricValue"] {
            color: #f8fafc !important;
        }
        div[data-testid="stMetricDelta"] > div {
            color: #cbd5e1 !important;
        }
        div[data-testid="stMetricDelta"] svg {
            fill: #94a3b8 !important;
        }
        div.net-asset-card div[data-testid="stMetric"] {
            background: linear-gradient(130deg, #0b3022 0%, #0f3f2f 100%) !important;
            border-color: #166534 !important;
            border-left: 6px solid #22c55e !important;
        }
        div.holding-asset-card div[data-testid="stMetric"] {
            background: linear-gradient(130deg, #0b223f 0%, #0f2f54 100%) !important;
            border-color: #1d4ed8 !important;
            border-left: 6px solid #3b82f6 !important;
        }
        .st-key-lev_metric_ok div[data-testid="stMetric"],
        .st-key-conc_metric_ok div[data-testid="stMetric"],
        .st-key-profit_metric_ok div[data-testid="stMetric"] {
            background: linear-gradient(130deg, #0f2a20 0%, #133428 100%) !important;
            border-color: #166534 !important;
            border-left: 6px solid #16a34a !important;
        }
        .st-key-lev_metric_bad div[data-testid="stMetric"],
        .st-key-conc_metric_bad div[data-testid="stMetric"],
        .st-key-profit_metric_bad div[data-testid="stMetric"] {
            background: linear-gradient(130deg, #3b1013 0%, #451417 100%) !important;
            border-color: #991b1b !important;
            border-left: 6px solid #ef4444 !important;
        }
        .st-key-cash_metric_wrap div[data-testid="stMetric"] {
            background: linear-gradient(130deg, #0f2a20 0%, #133428 100%) !important;
            border-color: #166534 !important;
            border-left: 6px solid #22c55e !important;
        }
        .st-key-debt_metric_low_wrap div[data-testid="stMetric"] {
            background: linear-gradient(130deg, #2f2611 0%, #3a2d12 100%) !important;
            border-color: #a16207 !important;
            border-left: 6px solid #f59e0b !important;
        }
        .st-key-debt_metric_mid_wrap div[data-testid="stMetric"] {
            background: linear-gradient(130deg, #3a1d12 0%, #4a1f14 100%) !important;
            border-color: #c2410c !important;
            border-left: 6px solid #f97316 !important;
        }
        .st-key-debt_metric_high_wrap div[data-testid="stMetric"] {
            background: linear-gradient(130deg, #3b1013 0%, #451417 100%) !important;
            border-color: #991b1b !important;
            border-left: 6px solid #ef4444 !important;
        }
        .st-key-cash_flat_metric_wrap div[data-testid="stMetric"] {
            background: linear-gradient(130deg, #111827 0%, #0f172a 100%) !important;
            border-color: #475569 !important;
            border-left: 6px solid #64748b !important;
        }
        div[data-testid="stRadio"] > div[role="radiogroup"] {
            background-color: #0f172a;
            border: 1px solid #334155;
        }
        div[data-testid="stRadio"] label[data-baseweb="radio"] > div {
            color: #94a3b8;
        }
        div[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) {
            background-color: #1e293b;
            box-shadow: none;
        }
        div[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) > div {
            color: #f8fafc !important;
        }
        div[data-testid="stDataFrame"],
        div[data-testid="stTable"] {
            border: 1px solid #334155;
            border-radius: 12px;
            background: #0f172a;
        }
        div[data-testid="stExpander"] {
            border-color: #334155 !important;
            background: #0f172a !important;
        }
        div[data-testid="stExpander"] details summary p {
            color: #cbd5e1 !important;
        }
        hr {
            border-color: #334155 !important;
        }
        </style>
        """,
        unsafe_allow_html=True
    )


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


def get_donation_qr_candidates():
    base = Path(__file__).resolve().parent
    return {
        "微信打赏": [
            base / "assets" / "donate" / "wechat_qr.png",
            base / "assets" / "wechat_qr.png",
            base / "wechat_qr.png",
        ],
        "支付宝打赏": [
            base / "assets" / "donate" / "alipay_qr.png",
            base / "assets" / "alipay_qr.png",
            base / "alipay_qr.png",
        ],
    }


def resolve_donation_qr_paths():
    resolved = {}
    for label, candidates in get_donation_qr_candidates().items():
        for p in candidates:
            if p.exists():
                resolved[label] = p
                break
    return resolved


@st.dialog("☕ 打赏支持")
def show_donation_dialog():
    qr_paths = resolve_donation_qr_paths()
    if not qr_paths:
        st.info("未检测到二维码图片。")
        return

    st.markdown(
        """
        <style>
        div[data-testid="stDialog"] div[role="dialog"]:has(.st-key-donate_dialog_body) {
            max-width: 540px !important;
            width: min(540px, 92vw) !important;
        }
        div[data-testid="stDialog"] div[role="dialog"]:has(.st-key-donate_dialog_body) [data-testid="stImage"] img {
            border-radius: 14px;
            box-shadow: 0 8px 22px rgba(15, 23, 42, 0.12);
        }
        @media (max-width: 768px) {
            div[data-testid="stDialog"] div[role="dialog"]:has(.st-key-donate_dialog_body) {
                width: 94vw !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    with st.container(key="donate_dialog_body"):
        for label in ["微信打赏", "支付宝打赏"]:
            path = qr_paths.get(label)
            if path is None:
                continue
            left, center, right = st.columns([0.19, 0.62, 0.19])
            with center:
                st.image(str(path), use_container_width=True)


def render_donation_section(dark_mode=False):
    if dark_mode:
        card_border = "#b45309"
        card_bg = "linear-gradient(135deg, #2a1b0f 0%, #3a220e 100%)"
        card_color = "#fef3c7"
        card_shadow = "0 10px 24px rgba(2, 6, 23, 0.32)"
        card_border_hover = "#f59e0b"
        card_shadow_hover = "0 16px 32px rgba(2, 6, 23, 0.48)"
        card_focus = "0 0 0 3px rgba(245, 158, 11, 0.35), 0 10px 24px rgba(2, 6, 23, 0.36)"
    else:
        card_border = "#fdba74"
        card_bg = "linear-gradient(135deg, #fff7ed 0%, #ffedd5 100%)"
        card_color = "#7c2d12"
        card_shadow = "0 10px 24px rgba(15, 23, 42, 0.08)"
        card_border_hover = "#fb923c"
        card_shadow_hover = "0 16px 32px rgba(15, 23, 42, 0.14)"
        card_focus = "0 0 0 3px rgba(251, 146, 60, 0.25), 0 10px 24px rgba(15, 23, 42, 0.08)"

    st.divider()
    donate_css = """
        <style>
        .st-key-donate_card_area div[data-testid="stButton"] > button {
            width: 100%;
            min-height: 92px;
            border-radius: 16px;
            border: 1px solid __BORDER__;
            background: __BG__;
            color: __COLOR__;
            font-weight: 800;
            font-size: 18px;
            letter-spacing: 0.2px;
            line-height: 1.35;
            white-space: pre-line;
            box-shadow: __SHADOW__;
            transition: transform 0.18s ease, box-shadow 0.18s ease, filter 0.18s ease;
        }
        .st-key-donate_card_area div[data-testid="stButton"] > button:hover {
            transform: translateY(-2px) scale(1.01);
            box-shadow: __SHADOW_HOVER__;
            filter: saturate(1.05);
            border-color: __BORDER_HOVER__;
        }
        .st-key-donate_card_area div[data-testid="stButton"] > button:focus {
            outline: none;
            box-shadow: __FOCUS_SHADOW__;
        }
        @media (max-width: 768px) {
            .st-key-donate_card_area div[data-testid="stButton"] > button {
                min-height: 80px;
                font-size: 15px;
            }
        }
        </style>
    """
    st.markdown(
        donate_css
        .replace("__BORDER__", card_border)
        .replace("__BG__", card_bg)
        .replace("__COLOR__", card_color)
        .replace("__SHADOW__", card_shadow)
        .replace("__SHADOW_HOVER__", card_shadow_hover)
        .replace("__BORDER_HOVER__", card_border_hover)
        .replace("__FOCUS_SHADOW__", card_focus),
        unsafe_allow_html=True,
    )

    with st.container(key="donate_card_area"):
        card_text = "☕ 这个工具帮到你了吗？请我喝杯咖啡吧"
        if st.button(card_text, key="donate_card_trigger", use_container_width=True):
            show_donation_dialog()


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
col_switch, col_privacy, col_dark, _ = st.columns([1, 1, 1, 2])
with col_switch:
    market_mode = st.radio("Market View", ["US", "CN"], horizontal=True, label_visibility="collapsed")
with col_privacy:
    st.toggle("隐私模式", key="privacy_mode", help="开启后隐藏所有金额")
with col_dark:
    st.toggle("夜间模式", key="dark_mode", help="开启后切换黑色主题")
privacy_mode = is_privacy_mode()
dark_mode = is_dark_mode()
_sync_modes_to_query(privacy_mode, dark_mode)
render_runtime_theme_css()

if privacy_mode:
    dark_target = "1" if dark_mode else "0"
    privacy_html = """
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
                <input type="hidden" name="dark" value="__DARK_TARGET__" />
                <button type="submit" title="点击关闭隐私模式">🙈 隐私中</button>
            </form>
        </div>
    """
    st.markdown(
        privacy_html.replace("__DARK_TARGET__", dark_target),
        unsafe_allow_html=True
    )

if dark_mode:
    privacy_target = "1" if privacy_mode else "0"
    dark_top = "calc(50% + 156px)" if privacy_mode else "50%"
    dark_bottom_mobile = "44px" if privacy_mode else "100px"
    dark_html = """
        <style>
        .dark-fab-left {
            position: fixed;
            left: 14px;
            top: __TOP__;
            transform: translateY(-50%);
            z-index: 9997;
        }
        .dark-fab-left form {
            margin: 0;
        }
        .dark-fab-left button {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            writing-mode: vertical-rl;
            text-orientation: mixed;
            gap: 6px;
            min-height: 124px;
            padding: 10px 10px;
            border-radius: 12px;
            border: 1px solid #64748b;
            background: linear-gradient(180deg, #1f2937 0%, #0f172a 100%);
            color: #e2e8f0;
            font-weight: 700;
            font-size: 12px;
            letter-spacing: 0.3px;
            text-decoration: none;
            box-shadow: 0 10px 24px rgba(2, 6, 23, 0.35);
            transition: transform 0.15s ease, box-shadow 0.15s ease, background 0.15s ease;
            cursor: pointer;
        }
        .dark-fab-left button:hover {
            transform: translateY(-2px);
            box-shadow: 0 14px 26px rgba(2, 6, 23, 0.45);
            background: linear-gradient(180deg, #334155 0%, #1e293b 100%);
        }
        @media (max-width: 768px) {
            .dark-fab-left {
                left: 8px;
                top: auto;
                bottom: __BOTTOM_MOBILE__;
                transform: none;
            }
            .dark-fab-left button {
                writing-mode: horizontal-tb;
                min-height: auto;
                padding: 8px 10px;
                border-radius: 10px;
            }
        }
        </style>
        <div class="dark-fab-left">
            <form method="get" action="">
                <input type="hidden" name="privacy" value="__PRIVACY_TARGET__" />
                <input type="hidden" name="dark" value="0" />
                <button type="submit" title="点击关闭夜间模式">🌙 夜间中</button>
            </form>
        </div>
    """
    st.markdown(
        dark_html
        .replace("__TOP__", dark_top)
        .replace("__BOTTOM_MOBILE__", dark_bottom_mobile)
        .replace("__PRIVACY_TARGET__", privacy_target),
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
with c1:
    lev_metric_key = "lev_metric_ok" if lev_color != "inverse" else "lev_metric_bad"
    with st.container(key=lev_metric_key):
        st.metric("⚖️ 杠杆率", f"{lev_ratio:.2f}x", delta=lev_delta, delta_color=lev_color)

# 集中度告警（类似杠杆率的做法）
conc_delta, conc_color = pf_service.concentration_status(top3_conc)
with c2:
    conc_metric_key = "conc_metric_ok" if conc_color == "normal" else "conc_metric_bad"
    with st.container(key=conc_metric_key):
        st.metric("🎯 Top3 集中度", f"{top3_conc:.1f}%", delta=conc_delta, delta_color=conc_color)

privacy_mode = is_privacy_mode()
cash_abs = abs(cash_balance)
if cash_balance < -1e-9:
    cash_title = "🏦 融资负债 (USD)"
    cash_value = fmt_money(cash_abs, 0)
    debt_ratio = (cash_abs / final_net_asset) if final_net_asset > 1e-9 else float("inf")
    if debt_ratio <= 0.2:
        debt_level = "低风险"
        cash_container_key = "debt_metric_low_wrap"
    elif debt_ratio <= 0.5:
        debt_level = "中风险"
        cash_container_key = "debt_metric_mid_wrap"
    else:
        debt_level = "高风险"
        cash_container_key = "debt_metric_high_wrap"

    if privacy_mode:
        cash_delta = f"负债占净资产 **** · {debt_level}"
    elif final_net_asset > 1e-9:
        cash_delta = f"负债占净资产 {debt_ratio * 100:.1f}% · {debt_level}"
    else:
        cash_delta = f"负债占净资产 N/A · {debt_level}"
elif cash_balance > 1e-9:
    cash_title = "💵 现金余额 (USD)"
    cash_value = fmt_money(cash_balance, 0)
    cash_delta = "现金占净资产 ****" if privacy_mode else f"现金占净资产 {cash_ratio:.1f}%"
    cash_container_key = "cash_metric_wrap"
else:
    cash_title = "💵 现金余额 (USD)"
    cash_value = fmt_money(0, 0)
    cash_delta = "现金占净资产 ****" if privacy_mode else "现金占净资产 0.0%"
    cash_container_key = "cash_flat_metric_wrap"

with c3:
    with st.container(key=cash_container_key):
        st.metric(
            cash_title,
            cash_value,
            cash_delta,
            delta_color="off",
            help="正值代表现金余额，负值代表融资负债。",
        )
with c4:
    profit_metric_key = "profit_metric_ok" if pnl >= 0 else "profit_metric_bad"
    with st.container(key=profit_metric_key):
        st.metric("🛡️ 总利润 (Profit)", fmt_money(pnl, 0), help="净资产 - 总投入本金")

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

        if dark_mode:
            holdings_wrap_bg = "#0b1220"
            holdings_wrap_border = "#334155"
            holdings_head_bg = "#111827"
            holdings_head_color = "#cbd5e1"
            holdings_row_border = "#1f2937"
            holdings_row_color = "#e2e8f0"
            holdings_row_hover = "#111827"
            holdings_track_bg = "#1e293b"
            holdings_track_border = "#334155"
            holdings_zero_color = "#94a3b8"
        else:
            holdings_wrap_bg = "#ffffff"
            holdings_wrap_border = "#e2e8f0"
            holdings_head_bg = "#f8fafc"
            holdings_head_color = "#334155"
            holdings_row_border = "#f1f5f9"
            holdings_row_color = "#0f172a"
            holdings_row_hover = "#f8fafc"
            holdings_track_bg = "#e2e8f0"
            holdings_track_border = "#cbd5e1"
            holdings_zero_color = "#64748b"

        st.markdown(
            f"""
            <style>
            .holdings-wrap {{ max-height: 450px; overflow: auto; border: 1px solid {holdings_wrap_border}; border-radius: 12px; background: {holdings_wrap_bg}; }}
            .holdings-table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
            .holdings-table thead th {{
                position: sticky; top: 0; z-index: 1;
                background: {holdings_head_bg}; color: {holdings_head_color}; font-weight: 700;
                text-align: left; padding: 10px 10px; border-bottom: 1px solid {holdings_wrap_border};
            }}
            .holdings-table tbody td {{
                padding: 9px 10px; border-bottom: 1px solid {holdings_row_border}; color: {holdings_row_color}; white-space: nowrap;
            }}
            .holdings-table tbody tr:hover {{ background: {holdings_row_hover}; }}
            .sm-wrap {{ display: flex; align-items: center; gap: 8px; width: 100%; }}
            .sm-track {{
                flex: 1 1 auto; min-width: 120px; height: 8px; border-radius: 999px; overflow: hidden;
                background: {holdings_track_bg}; border: 1px solid {holdings_track_border};
            }}
            .sm-fill {{ height: 100%; border-radius: 999px; filter: saturate(0.72); }}
            .sm-fill.sm-pos {{ background: linear-gradient(90deg, rgba(34, 197, 94, 0.82), rgba(22, 163, 74, 0.82)); }}
            .sm-fill.sm-neg {{ background: linear-gradient(90deg, rgba(248, 113, 113, 0.82), rgba(220, 38, 38, 0.82)); }}
            .sm-fill.sm-zero {{ background: rgba(148, 163, 184, 0.9); }}
            .sm-label {{ font-weight: 400; font-size: 13px; min-width: 56px; text-align: right; }}
            .sm-label.sm-pos {{ color: rgba(22, 163, 74, 0.86); }}
            .sm-label.sm-neg {{ color: rgba(220, 38, 38, 0.86); }}
            .sm-label.sm-zero {{ color: {holdings_zero_color}; }}
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
if "chart_mode_toggle" not in st.session_state:
    st.session_state["chart_mode_toggle"] = "%"
elif st.session_state.get("chart_mode_toggle") not in ["$", "%"]:
    st.session_state["chart_mode_toggle"] = "%"

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

ui.render_history_chart(
    history_df,
    mode=mode_key,
    mask_value=privacy_mode,
    dark_mode=dark_mode
)

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
        mask_value=privacy_mode,
        dark_mode=dark_mode,
    )

with cal_left:
    period_stats = ui.get_pnl_period_stats(history_df)
    anchor_date = period_stats["anchor_date"]
    # 与右侧筛选控件行做高度对齐，卡片从日历主体同一水平线开始
    st.markdown('<div style="height:46px;"></div>', unsafe_allow_html=True)
    if dark_mode:
        side_shadow = "0 10px 20px rgba(2, 6, 23, 0.45)"
        side_title_color = "#cbd5e1"
    else:
        side_shadow = "0 10px 20px rgba(15, 23, 42, 0.16)"
        side_title_color = "#334155"
    side_css = """
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
            box-shadow: __SIDE_SHADOW__;
            filter: saturate(1.04);
        }
        .pnl-side-title {
            font-size: 11px;
            color: __SIDE_TITLE_COLOR__;
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
    """
    st.markdown(
        side_css.replace("__SIDE_SHADOW__", side_shadow).replace("__SIDE_TITLE_COLOR__", side_title_color),
        unsafe_allow_html=True
    )

    def _period_card_style(val):
        if dark_mode:
            if val > 0:
                return ("linear-gradient(135deg, #0f2a20 0%, #133428 100%)", "#22c55e", "#86efac")
            if val < 0:
                return ("linear-gradient(135deg, #3b1013 0%, #451417 100%)", "#ef4444", "#fca5a5")
            return ("linear-gradient(135deg, #111827 0%, #1e293b 100%)", "#64748b", "#cbd5e1")
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

# --- 7. 打赏支持 ---
render_donation_section(dark_mode=dark_mode)

# 底部悬浮按钮
st.markdown('<span id="fab-anchor"></span>', unsafe_allow_html=True)
with st.container(key="fab_wrap"):
    if st.button("➕", key="fab_main"):
        show_add_modal()
