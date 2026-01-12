# app.py
# (请完全覆盖原文件)

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
from datetime import date, datetime
import data_manager as db

# ================= 1. 页面配置与 CSS =================
st.set_page_config(page_title="我的投资管理 Pro", layout="wide")
db.init_db()

# CSS 修复：强制居中对齐
st.markdown("""
    <style>
    /* 强制表头和单元格居中 */
    th, td {
        text-align: center !important;
    }
    .stDataFrame { text-align: center !important; }

    /* 针对 data_editor 的特殊修正 */
    div[data-testid="stDataEditor"] div[role="grid"] {
        text-align: center !important;
    }

    /* 悬浮按钮 */
    div.stButton.fixed-fab > button {
        border-radius: 50%;
        width: 60px;
        height: 60px;
        font-size: 30px;
        background-color: #FF4B4B;
        color: white;
        box-shadow: 2px 2px 10px rgba(0,0,0,0.3);
        border: none;
    }
    </style>
""", unsafe_allow_html=True)


# ================= 2. 工具函数 =================
def get_realtime_price(symbol):
    symbol = symbol.lower().strip()
    headers = {'Referer': 'https://finance.sina.com.cn'}
    try:
        if symbol.isalpha():
            url = f"https://hq.sinajs.cn/list=gb_{symbol}"
            resp = requests.get(url, headers=headers)
            content = resp.text.split('="')[1].split(',')
            if len(content) > 1: return float(content[1])
        else:
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


# ================= 3. 弹窗逻辑 =================
@st.dialog("📝 操作中心")
def show_add_modal():
    tab1, tab2, tab3 = st.tabs(["股票交易", "资金进出", "♻️ 回收站"])

    with tab1:
        with st.form("add_trade_form"):
            c1, c2 = st.columns(2)
            t_date = c1.date_input("日期", date.today())
            t_sym = c2.text_input("代码", "NVDA").upper()
            c3, c4 = st.columns(2)
            t_type = c3.selectbox("方向", ["BUY", "SELL"])
            t_qty = c4.number_input("数量", 0.0, step=1.0)
            c5, c6 = st.columns(2)
            t_price = c5.number_input("单价", 0.0, step=0.1)
            t_fee = c6.number_input("佣金", 0.0)
            t_note = st.text_input("笔记", placeholder="例如：财报前加仓")
            if st.form_submit_button("提交交易", use_container_width=True):
                db.add_transaction(t_date, t_sym, t_type, t_qty, t_price, t_fee, t_note)
                st.success("已保存")
                st.rerun()

    with tab2:
        with st.form("fund_form"):
            f_date = st.date_input("日期", date.today())
            f_type = st.selectbox("类型", ["DEPOSIT", "WITHDRAW"],
                                  format_func=lambda x: "入金 (增加投入)" if x == "DEPOSIT" else "出金 (减少投入)")
            f_amount = st.number_input("金额", 1000.0, step=100.0)
            if st.form_submit_button("提交", use_container_width=True):
                db.add_fund_flow(f_date, f_type, f_amount, "")
                st.success("已保存")
                st.rerun()

        # --- Tab 3: 回收站 (修复版) ---
    with tab3:
        st.caption("最近 7 天删除的记录")
        deleted_df = db.get_deleted_transactions_last_7_days()

        if not deleted_df.empty:
            # 增加一个简单的表头
            st.markdown(
                """<div style="display: flex; justify-content: space-between; padding-bottom: 5px; font-weight: bold; border-bottom: 1px solid #eee; margin-bottom: 10px;">
                    <span style="flex: 4;">交易详情</span>
                    <span style="flex: 1; text-align: right;">操作</span>
                </div>""",
                unsafe_allow_html=True
            )

            for idx, row in deleted_df.iterrows():
                # 1. 布局核心：5:1 比例，并且垂直居中
                c_info, c_btn = st.columns([5, 1], vertical_alignment="center")

                with c_info:
                    # 使用 HTML 美化显示：日期变灰，代码加粗，买卖变色
                    color = "red" if row['type'] == 'BUY' else "green"
                    st.markdown(
                        f"""
                        <div style="font-size: 14px;">
                            <span style="color: #888; margin-right: 8px;">{row['date']}</span>
                            <strong>{row['symbol']}</strong> 
                            <span style="color: {color}; font-weight: bold; margin: 0 5px;">{row['type']}</span> 
                            <span>({int(row['quantity'])})</span>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                with c_btn:
                    # 2. 恢复按钮：放置在右侧
                    # key 必须唯一，加上 idx 防止冲突
                    if st.button("恢复", key=f"restore_btn_{row['id']}"):
                        db.restore_transaction(row['id'])
                        st.toast(f"✅ 已恢复 {row['symbol']} 交易", icon="↩️")
                        st.rerun()

                # 每行加个浅分割线
                st.markdown("<hr style='margin: 5px 0; border: 0; border-top: 1px solid #f0f0f0;'>",
                            unsafe_allow_html=True)
        else:
            st.info("🗑️ 回收站是空的")


# ================= 4. 侧边栏 =================
with st.sidebar:
    st.title("💰 投资组合")
    page = st.radio("导航", ["资产看板", "收益日历"], label_visibility="collapsed")
    st.divider()

# ================= 5. 主页面 =================
if page == "资产看板":
    st.subheader("🏠 资产总览")

    portfolio_df = db.get_portfolio_summary()
    total_invested = db.get_total_invested()

    if not portfolio_df.empty:
        if 'last_update' not in st.session_state:
            p_bar = st.progress(0, text="更新行情...")
            current_prices = []
            market_values = []
            for i, row in portfolio_df.iterrows():
                price = get_realtime_price(row['Symbol'])
                if price is None: price = 0
                current_prices.append(price)
                market_values.append(price * row['Quantity'])
                p_bar.progress((i + 1) / len(portfolio_df))
            p_bar.empty()
            portfolio_df['Price'] = current_prices
            portfolio_df['Market Value'] = market_values
            st.session_state['portfolio_cache'] = portfolio_df
            st.session_state['last_update'] = datetime.now()
        else:
            portfolio_df = st.session_state['portfolio_cache']

        total_asset = sum(portfolio_df['Market Value'])
        total_pnl = total_asset - total_invested
        ret_rate = (total_pnl / total_invested * 100) if total_invested > 0 else 0
        db.save_daily_snapshot(date.today().strftime('%Y-%m-%d'), total_asset, total_invested)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("总资产", f"${total_asset:,.0f}")
        c2.metric("总投入", f"${total_invested:,.0f}")
        c3.metric("总收益", f"${total_pnl:,.0f}", delta_color="normal")
        c4.metric("总收益率", f"{ret_rate:.2f}%", delta=f"{ret_rate:.2f}%")
        st.divider()

        col_chart1, col_chart2 = st.columns(2)
        with col_chart1:
            st.caption("持仓分布")
            fig = px.pie(portfolio_df, values='Market Value', names='Symbol', hole=0.5)
            fig.update_layout(margin=dict(t=0, b=0, l=0, r=0))
            st.plotly_chart(fig, use_container_width=True)
        with col_chart2:
            st.caption("持仓明细")
            display_df = portfolio_df[['Symbol', 'Quantity', 'Avg Cost', 'Price', 'Market Value']].copy()
            st.dataframe(
                display_df.style.format({
                    "Avg Cost": "{:.2f}",
                    "Price": "{:.2f}",
                    "Market Value": "{:.0f}"
                }), use_container_width=True, height=300
            )
    else:
        st.info("👋 欢迎！点击右下角 ➕ 开始使用。")

    # === 交易流水 (交互删除核心修复) ===
    st.subheader("📋 交易流水")
    all_trans = db.get_all_transactions(include_deleted=False)

    if not all_trans.empty:
        # 显式重置索引，确保 iloc 定位准确
        all_trans = all_trans.reset_index(drop=True)

        # 准备显示数据，确保 ID 存在于数据中但可能不在 columns_config 里显示
        # 注意：这里我们只取需要的列，防止 note 缺失
        cols_to_show = ['id', 'date', 'symbol', 'type', 'quantity', 'price', 'fee', 'note']
        # 确保 DataFrame 里有 note 列，如果没有（旧数据问题），补一个空列防止报错
        if 'note' not in all_trans.columns:
            all_trans['note'] = ""

        display_trans = all_trans[cols_to_show].copy()

        edited_df = st.data_editor(
            display_trans,
            column_config={
                "id": None,  # 隐藏ID
                "date": "日期",
                "symbol": "代码",
                "type": "方向",
                "quantity": st.column_config.NumberColumn("数量", format="%.0f"),
                "price": st.column_config.NumberColumn("价格", format="$%.2f"),
                "fee": st.column_config.NumberColumn("费用", format="$%.1f"),
                "note": st.column_config.TextColumn("笔记", width="medium"),
            },
            hide_index=True,
            use_container_width=True,
            num_rows="dynamic",
            key="trans_editor_widget"  # 更改 key 避免缓存冲突
        )

        # 捕获删除事件
        if st.session_state.get("trans_editor_widget"):
            changes = st.session_state["trans_editor_widget"]
            if changes.get("deleted_rows"):
                deleted_indices = changes["deleted_rows"]
                for idx in deleted_indices:
                    # 关键修复：
                    # 1. 使用 iloc 定位正确行
                    # 2. 获取 ID 并强制转为 int
                    try:
                        raw_id = display_trans.iloc[idx]['id']
                        db.soft_delete_transaction(int(raw_id))
                    except IndexError:
                        pass  # 防止索引越界

                # 清除缓存强制刷新
                if 'last_update' in st.session_state: del st.session_state['last_update']
                st.rerun()
    else:
        st.caption("暂无历史交易")

elif page == "收益日历":
    st.subheader("📅 收益复盘")
    history_df = db.get_history_data()
    if not history_df.empty:
        history_df['date'] = pd.to_datetime(history_df['date'])
        history_df = history_df.sort_values('date')
        history_df['daily_profit'] = history_df['total_pnl'].diff().fillna(0)
        history_df['daily_pct'] = (history_df['total_asset'].pct_change() * 100).fillna(0)

        c_opt1, c_opt2 = st.columns([1, 5])
        view_type = c_opt1.radio("显示单位", ["收益额 ($)", "收益率 (%)"])
        target_col = 'daily_profit' if "收益额" in view_type else 'daily_pct'

        fig_line = px.line(history_df, x='date', y='total_pnl', title="累计盈亏曲线", markers=True)
        st.plotly_chart(fig_line, use_container_width=True)

        history_df['Month'] = history_df['date'].dt.to_period('M').astype(str)
        monthly_data = history_df.groupby('Month')[target_col].sum().reset_index()
        monthly_data['color'] = monthly_data[target_col].apply(lambda x: '#ff4b4b' if x < 0 else '#00c853')

        st.write("#### 月度表现")
        fig_bar = go.Figure(
            go.Bar(x=monthly_data['Month'], y=monthly_data[target_col], marker_color=monthly_data['color']))
        st.plotly_chart(fig_bar, use_container_width=True)
    else:
        st.warning("暂无历史数据")

# ================= 6. 悬浮按钮 =================
# ... (前面的代码不变)

# ================= 6. 悬浮按钮 (CSS 修复版) =================
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