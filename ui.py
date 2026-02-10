import streamlit as st  # 🔥 必须加这行，用于显示调试信息
from streamlit_echarts import st_echarts
import pandas as pd
import numpy as np      # 🔥 必须加这行，否则数学计算会报错
import calendar
from datetime import datetime, timedelta

# 🔥 ECharts 3D 饼图 (支持隐私脱敏 mask_value)
def render_echarts_pie(df, name_col, value_col, title_text="", key=None, mask_value=False, color_palette=None):
    """
    增加了 mask_value 参数以兼容 app.py 的调用。
    当前配置下 tooltip 已关闭，且标签只显示名称和百分比，本身已具备隐私性。
    """
    # 🔥 1. 核心修改：按金额/占比从大到小排序
    df_sorted = df.sort_values(by=value_col, ascending=False)

    # 2. 计算总资产
    total_val = df_sorted[value_col].astype(float).sum()

    # 3. 生成数据列表 (此时数据已经是排好序的)
    data_list = []
    for _, row in df_sorted.iterrows():
        val = int(row[value_col])
        pct = (val / total_val * 100) if total_val > 0 else 0
        # 补齐空格保持视觉对齐
        name_with_pct = f"{str(row[name_col])}  {pct:.1f}%"
        data_list.append({"value": val, "name": name_with_pct})

    options = {
        # 🔥 1. 彻底关闭悬浮提示框 (Tooltip)，防止显示具体金额
        "tooltip": {"show": False},

        "legend": {
            "show": True,
            "orient": "vertical",
            "right": "0%",
            "bottom": "5%",
            "itemGap": 10,
            "textStyle": {"fontSize": 12, "color": "#475569", "fontWeight": "bold"}
        },

        "series": [{
            "name": title_text,
            "type": "pie",
            "radius": ["40%", "70%"],
            "center": ["40%", "50%"],

            "avoidLabelOverlap": False,

            "itemStyle": {"borderRadius": 8, "borderColor": "#fff", "borderWidth": 2},

            # 🔥 2. 核心修正：默认状态下，把标签“藏”在圆心
            "label": {
                "show": False,
                "position": "center"
            },

            "emphasis": {
                "label": {
                    "show": True,
                    "fontSize": 18,
                    "fontWeight": "bold",
                    # 这里定义中间显示什么：{b}=名字(含百分比)
                    "formatter": "{b}",
                    "color": "#333"
                },
                "scale": True,
                "scaleSize": 10,
                "itemStyle": {"shadowBlur": 10, "shadowOffsetX": 0, "shadowColor": "rgba(0, 0, 0, 0.2)"}
            },
            "data": data_list
        }]
    }

    if color_palette:
        options["color"] = color_palette

    st_echarts(options=options, height="280px", key=key)


# 🔥 历史曲线图 (支持隐私脱敏 mask_value)
def render_history_chart(history_df, mode='value', mask_value=False):
    """
    稳健版：移除复杂特效，强制显示数据点。
    增加 mask_value 逻辑：隐藏金额数值。
    """
    if history_df is None or history_df.empty:
        return

    # 1. 数据清洗
    try:
        df = history_df.copy()
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date')

        # 强制转 float
        df['total_asset'] = pd.to_numeric(df['total_asset'], errors='coerce').fillna(0.0)
        df['total_invested'] = pd.to_numeric(df['total_invested'], errors='coerce').fillna(0.0)

        dates = df['date'].dt.strftime('%Y-%m-%d').tolist()

    except Exception:
        return

    options = {}

    # ================= 模式 A: 资产绝对值 ($) =================
    if mode == 'value':
        assets = [float(round(x, 2)) for x in df['total_asset'].values]
        principals = [float(round(x, 2)) for x in df['total_invested'].values]

        # 🔥🔥🔥 隐私模式核心逻辑 🔥🔥🔥
        if mask_value:
            # 脱敏状态：显示星号
            tooltip_fmt = "<b>📅 {b}</b><br/>💰 净资产: <b>****</b><br/>🏦 总本金: <b>****</b>"
            y_axis_label = "****"
        else:
            # 正常状态：显示金额
            tooltip_fmt = "<b>📅 {b}</b><br/>💰 净资产: <b>${c0}</b><br/>🏦 总本金: <b>${c1}</b>"
            y_axis_label = "${value}"

        options = {
            "tooltip": {
                "trigger": 'axis',
                "backgroundColor": "rgba(255,255,255,0.95)",
                "textStyle": {"color": "#333"},
                "formatter": tooltip_fmt  # 应用格式
            },
            "legend": {"data": ["净资产", "总本金"], "top": "0%"},
            "grid": {"top": "15%", "left": "2%", "right": "4%", "bottom": "5%", "containLabel": True},
            "xAxis": {
                "type": 'category',
                "boundaryGap": False,
                "data": dates,
                "axisLine": {"show": False},
                "axisTick": {"show": False},
                "axisLabel": {"color": "#94a3b8"}
            },
            "yAxis": {
                "type": 'value',
                "scale": True,
                "splitLine": {"lineStyle": {"type": "dashed", "color": "#f1f5f9"}},
                "axisLabel": {"formatter": y_axis_label, "color": "#94a3b8"} # 应用脱敏标签
            },
            "series": [
                {
                    "name": "净资产",
                    "type": "line",
                    "smooth": 0.2,
                    "showSymbol": True,
                    "symbolSize": 6,
                    "lineStyle": {"width": 3, "color": "#16a34a"},
                    "itemStyle": {"color": "#16a34a"},
                    "data": assets
                },
                {
                    "name": "总本金",
                    "type": "line",
                    "smooth": 0.2,
                    "showSymbol": False,
                    "lineStyle": {"width": 2, "color": "#94a3b8", "type": "dashed"},
                    "itemStyle": {"color": "#94a3b8"},
                    "data": principals
                }
            ]
        }

    # ================= 模式 B: 收益率百分比 (%) =================
    else:
        # 收益率本身就是相对值，不需要脱敏，保持原样即可
        yields = []
        for i, row in df.iterrows():
            inv = float(row['total_invested'])
            ass = float(row['total_asset'])

            val = 0.0
            if inv > 1.0:
                val = (ass - inv) / inv * 100.0

            if np.isnan(val) or np.isinf(val):
                val = 0.0

            yields.append(float(round(val, 2)))

        options = {
            "tooltip": {
                "trigger": 'axis',
                "backgroundColor": "rgba(255,255,255,0.95)",
                "textStyle": {"color": "#333"},
                "formatter": "<b>📅 {b}</b><br/>🚀 累计收益: <b>{c}%</b>"
            },
            "grid": {"top": "15%", "left": "2%", "right": "4%", "bottom": "5%", "containLabel": True},
            "xAxis": {
                "type": 'category',
                "boundaryGap": False,
                "data": dates,
                "axisLine": {"show": False},
                "axisTick": {"show": False},
                "axisLabel": {"color": "#94a3b8"}
            },
            "yAxis": {
                "type": 'value',
                "scale": True,
                "splitLine": {"lineStyle": {"type": "dashed", "color": "#f1f5f9"}},
                "axisLabel": {"formatter": "{value}%", "color": "#94a3b8"}
            },
            "series": [{
                "name": '累计收益率',
                "type": 'line',
                "smooth": 0.2,
                "showSymbol": True,
                "symbolSize": 6,
                "lineStyle": {"width": 3, "color": "#ea580c"},
                "itemStyle": {"color": "#ea580c"},
                "markLine": {
                    "symbol": "none",
                    "data": [{"yAxis": 0}],
                    "label": {"show": True, "position": "end", "formatter": "0%", "color": "#94a3b8"},
                    "lineStyle": {"color": "#64748b", "type": "solid", "width": 1}
                },
                "areaStyle": {
                    "opacity": 0.1,
                    "color": "#ea580c"
                },
                "data": yields
            }]
        }

    st_echarts(options=options, height="350px", key=f"chart_history_{mode}")


def get_pnl_calendar_options(history_df):
    """返回收益日历可用年份及默认年月。"""
    now = datetime.now()
    if history_df is None or history_df.empty:
        return [now.year], now.year, now.month

    df = history_df.copy()
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df = df.dropna(subset=['date']).sort_values('date')
    if df.empty:
        return [now.year], now.year, now.month

    years = sorted(df['date'].dt.year.unique().tolist())
    last_date = df['date'].max()
    return years, int(last_date.year), int(last_date.month)


def get_pnl_week_options(history_df, year=None):
    """返回周视图可选周列表与默认周起始日(YYYY-MM-DD)。"""
    daily_df = _prepare_daily_pnl(history_df)
    now = datetime.now()
    default_week_start = (now - timedelta(days=now.weekday())).strftime('%Y-%m-%d')
    if daily_df.empty:
        return [(default_week_start, f"W{now.isocalendar()[1]:02d} {now:%m/%d}-{(now + timedelta(days=6-now.weekday())):%m/%d}")], default_week_start

    tmp = daily_df.copy()
    tmp['week_start'] = tmp['date'].dt.normalize() - pd.to_timedelta(tmp['date'].dt.weekday, unit='D')
    tmp['iso_year'] = tmp['date'].dt.isocalendar().year.astype(int)
    tmp['iso_week'] = tmp['date'].dt.isocalendar().week.astype(int)

    if year is not None:
        filtered = tmp[tmp['iso_year'] == int(year)]
        if not filtered.empty:
            tmp = filtered

    week_rows = (
        tmp[['week_start', 'iso_year', 'iso_week']]
        .drop_duplicates()
        .sort_values('week_start')
    )
    options = []
    for _, row in week_rows.iterrows():
        start = pd.to_datetime(row['week_start']).to_pydatetime()
        end = start + timedelta(days=6)
        key = start.strftime('%Y-%m-%d')
        label = f"W{int(row['iso_week']):02d} {start:%m/%d}-{end:%m/%d}"
        options.append((key, label))

    if not options:
        return [(default_week_start, f"W{now.isocalendar()[1]:02d} {now:%m/%d}-{(now + timedelta(days=6-now.weekday())):%m/%d}")], default_week_start

    return options, options[-1][0]


def _prepare_daily_pnl(history_df):
    if history_df is None or history_df.empty:
        return pd.DataFrame()

    df = history_df.copy()
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df['total_asset'] = pd.to_numeric(df['total_asset'], errors='coerce')
    df = df.dropna(subset=['date', 'total_asset']).sort_values('date')
    if df.empty:
        return pd.DataFrame()

    # daily_snapshots 按日期唯一，但这里仍按日期去重兜底
    df = df.groupby(df['date'].dt.date, as_index=False).last()
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date')

    df['daily_amount'] = df['total_asset'].diff().fillna(0.0)
    prev_asset = df['total_asset'].shift(1)
    df['daily_rate'] = np.where(prev_asset > 0, (df['daily_amount'] / prev_asset) * 100.0, 0.0)
    df['daily_rate'] = df['daily_rate'].replace([np.inf, -np.inf], 0).fillna(0.0)
    df['day_key'] = df['date'].dt.strftime('%Y-%m-%d')
    return df[['day_key', 'daily_amount', 'daily_rate', 'date']]


def get_pnl_period_stats(history_df):
    """
    返回截至最新快照日的本周/本月/今年收益统计。
    返回结构:
    {
        "anchor_date": datetime.date,
        "week": {"amount": float, "rate": float},
        "month": {"amount": float, "rate": float},
        "year": {"amount": float, "rate": float},
    }
    """
    daily_df = _prepare_daily_pnl(history_df)
    if daily_df.empty:
        today = datetime.now().date()
        return {
            "anchor_date": today,
            "week": {"amount": 0.0, "rate": 0.0},
            "month": {"amount": 0.0, "rate": 0.0},
            "year": {"amount": 0.0, "rate": 0.0},
        }

    latest_ts = pd.to_datetime(daily_df["date"]).max()
    anchor = latest_ts.date()
    week_start = (latest_ts - timedelta(days=latest_ts.weekday())).normalize()
    month_start = latest_ts.replace(day=1).normalize()
    year_start = latest_ts.replace(month=1, day=1).normalize()

    def calc(start_ts):
        scoped = daily_df[(daily_df["date"] >= start_ts) & (daily_df["date"] <= latest_ts)]
        if scoped.empty:
            return {"amount": 0.0, "rate": 0.0}
        amount = float(scoped["daily_amount"].sum())
        rate = float(((1 + (scoped["daily_rate"] / 100.0)).prod() - 1) * 100.0)
        return {"amount": amount, "rate": rate}

    return {
        "anchor_date": anchor,
        "week": calc(week_start),
        "month": calc(month_start),
        "year": calc(year_start),
    }


def _prepare_monthly_pnl(daily_df):
    if daily_df is None or daily_df.empty:
        return pd.DataFrame({
            'month': list(range(1, 13)),
            'monthly_amount': [0.0] * 12,
            'monthly_rate': [0.0] * 12
        })

    tmp = daily_df.copy()
    tmp['month'] = tmp['date'].dt.month.astype(int)

    amount_df = tmp.groupby('month', as_index=False).agg(
        monthly_amount=('daily_amount', 'sum')
    )
    rate_df = tmp.groupby('month', as_index=False).agg(
        monthly_rate=('daily_rate', lambda s: ((1 + (s / 100.0)).prod() - 1) * 100.0 if len(s) > 0 else 0.0)
    )

    merged = amount_df.merge(rate_df, on='month', how='outer').fillna(0.0)
    full_months = pd.DataFrame({'month': list(range(1, 13))})
    merged = full_months.merge(merged, on='month', how='left').fillna(0.0)
    return merged.sort_values('month')


def _fmt_amount(value, mask_value):
    if mask_value:
        return "****"
    return f"{value:+,.2f}"


def _fmt_rate(value):
    return f"{value:+.2f}%"


def _value_color(value):
    if value > 0:
        return "#16a34a"
    if value < 0:
        return "#dc2626"
    return "#475569"


def _cell_bg(value, max_abs):
    if max_abs <= 0:
        return "rgba(148, 163, 184, 0.08)"
    ratio = min(abs(value) / max_abs, 1.0)
    alpha = 0.10 + ratio * 0.30
    if value > 0:
        return f"rgba(34, 197, 94, {alpha:.2f})"
    if value < 0:
        return f"rgba(239, 68, 68, {alpha:.2f})"
    return "rgba(148, 163, 184, 0.10)"


def _render_calendar_hover_css():
    st.markdown(
        """
        <style>
        .pnl-calendar-host .pnl-tile {
            transition: transform 0.16s ease, box-shadow 0.16s ease;
            transform-origin: center;
            will-change: transform;
            position: relative;
            z-index: 0;
        }
        .pnl-calendar-host .pnl-tile:hover {
            transform: scale(1.06);
            box-shadow: 0 10px 20px rgba(15, 23, 42, 0.18);
            z-index: 5;
        }
        .pnl-calendar-host .pnl-tile-no-data:hover {
            transform: none;
            box-shadow: none;
            z-index: 0;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_month(year, month, daily_map, metric_mode, max_abs, mask_value=False):
    month_name = f"{year}-{month:02d}"
    cal = calendar.Calendar(firstweekday=0)
    week_days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    today_date = datetime.now().date()

    html_parts = [
        '<div class="pnl-calendar-host" style="width:100%;margin:0 0 12px 0;border:1px solid #e2e8f0;'
        'border-radius:10px;padding:10px;background:#ffffff;">'
    ]
    html_parts.append(
        f'<div style="font-weight:700;font-size:14px;color:#1e293b;margin-bottom:8px;">{month_name}</div>'
    )
    html_parts.append('<div style="display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:6px;">')

    for wd in week_days:
        html_parts.append(
            f'<div style="font-size:13px;font-weight:800;color:#334155;'
            f'text-align:center;padding:6px 0;">{wd}</div>'
        )

    for week in cal.monthdatescalendar(year, month):
        for day_obj in week:
            if day_obj.month != month:
                html_parts.append(
                    '<div class="pnl-tile pnl-tile-no-data" style="min-height:68px;border:1px solid #e2e8f0;border-radius:14px;'
                    'background:#f8fafc;"></div>'
                )
                continue

            day_key = day_obj.strftime('%Y-%m-%d')
            item = daily_map.get(day_key)
            if item is None:
                value = 0.0
                display_val = "--" if day_obj <= today_date else ""
                tile_cls = "pnl-tile pnl-tile-no-data"
            else:
                value = item['daily_amount'] if metric_mode == 'amount' else item['daily_rate']
                display_val = _fmt_amount(value, mask_value) if metric_mode == 'amount' else _fmt_rate(value)
                tile_cls = "pnl-tile"

            bg = _cell_bg(value, max_abs)
            value_color = _value_color(value)
            html_parts.append(
                f'<div class="{tile_cls}" style="min-height:68px;border:1px solid #e2e8f0;border-radius:14px;'
                f'padding:8px 6px;background:{bg};display:flex;flex-direction:column;'
                'align-items:center;justify-content:center;gap:8px;box-shadow:inset 0 1px 0 rgba(255,255,255,0.35);">'
                f'<div style="font-size:15px;font-weight:800;color:#1e293b;line-height:1;text-align:center;">{day_obj.day:02d}</div>'
                f'<div style="font-size:12px;font-weight:400;color:{value_color};line-height:1.15;text-align:center;">{display_val}</div>'
                '</div>'
            )

    html_parts.append('</div></div>')
    st.markdown("".join(html_parts), unsafe_allow_html=True)


def _render_week(week_start, daily_map, metric_mode, max_abs, mask_value=False):
    start = pd.to_datetime(week_start).to_pydatetime()
    end = start + timedelta(days=6)
    week_days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    today_date = datetime.now().date()

    html_parts = [
        '<div class="pnl-calendar-host" style="width:100%;margin:0 0 12px 0;border:1px solid #e2e8f0;'
        'border-radius:10px;padding:10px;background:#ffffff;">'
    ]
    html_parts.append(
        f'<div style="font-weight:700;font-size:14px;color:#1e293b;margin-bottom:8px;">'
        f'Week {start:%Y-%m-%d} ~ {end:%Y-%m-%d}</div>'
    )
    html_parts.append('<div style="display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:4px;">')

    for wd in week_days:
        html_parts.append(
            f'<div style="font-size:12px;font-weight:800;color:#334155;'
            f'text-align:center;padding:4px 0;">{wd}</div>'
        )

    for i in range(7):
        day_obj = start + timedelta(days=i)
        day_key = day_obj.strftime('%Y-%m-%d')
        item = daily_map.get(day_key)
        if item is None:
            value = 0.0
            display_val = "--" if day_obj.date() <= today_date else ""
            tile_cls = "pnl-tile pnl-tile-no-data"
        else:
            value = item['daily_amount'] if metric_mode == 'amount' else item['daily_rate']
            display_val = _fmt_amount(value, mask_value) if metric_mode == 'amount' else _fmt_rate(value)
            tile_cls = "pnl-tile"

        bg = _cell_bg(value, max_abs)
        value_color = _value_color(value)
        html_parts.append(
            f'<div class="{tile_cls}" style="min-height:56px;border:1px solid #e2e8f0;border-radius:12px;'
            f'padding:6px 4px;background:{bg};display:flex;flex-direction:column;'
            'align-items:center;justify-content:center;gap:6px;box-shadow:inset 0 1px 0 rgba(255,255,255,0.35);">'
            f'<div style="font-size:13px;font-weight:800;color:#1e293b;line-height:1;text-align:center;">{day_obj.day:02d}</div>'
            f'<div style="font-size:11px;font-weight:400;color:{value_color};line-height:1.15;text-align:center;">{display_val}</div>'
            '</div>'
        )

    html_parts.append('</div></div>')
    st.markdown("".join(html_parts), unsafe_allow_html=True)


def _render_year_cards(year, monthly_df, metric_mode, months_with_data=None, mask_value=False):
    months_with_data = set(months_with_data or [])
    monthly_map = {}
    for _, row in monthly_df.iterrows():
        monthly_map[int(row['month'])] = {
            'monthly_amount': float(row['monthly_amount']),
            'monthly_rate': float(row['monthly_rate'])
        }

    metric_key = 'monthly_amount' if metric_mode == 'amount' else 'monthly_rate'
    values = [monthly_map.get(m, {metric_key: 0.0})[metric_key] for m in range(1, 13)]
    max_abs = float(max(abs(v) for v in values)) if values else 0.0

    html_parts = [
        '<div class="pnl-calendar-host" style="width:100%;margin:0 0 12px 0;">'
        '<div style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;">'
    ]

    for month in range(1, 13):
        item = monthly_map.get(month, {'monthly_amount': 0.0, 'monthly_rate': 0.0})
        value = item['monthly_amount'] if metric_mode == 'amount' else item['monthly_rate']
        display_val = _fmt_amount(value, mask_value) if metric_mode == 'amount' else _fmt_rate(value)
        bg = _cell_bg(value, max_abs)
        value_color = _value_color(value)
        tile_cls = "pnl-tile" if month in months_with_data else "pnl-tile pnl-tile-no-data"
        html_parts.append(
            f'<div class="{tile_cls}" style="border:1px solid #e2e8f0;border-radius:12px;padding:14px 14px;'
            f'background:{bg};">'
            f'<div style="font-size:13px;color:#334155;margin-bottom:8px;">{year}-{month:02d}</div>'
            f'<div style="font-size:16px;font-weight:400;color:{value_color};">{display_val}</div>'
            '</div>'
        )

    html_parts.append('</div></div>')
    st.markdown("".join(html_parts), unsafe_allow_html=True)


def render_pnl_calendar(history_df, view_mode='month', metric_mode='amount', year=None, month=None, week_start=None, mask_value=False):
    """
    收益日历：
    - view_mode: month/year
    - metric_mode: amount/rate
    """
    daily_df = _prepare_daily_pnl(history_df)
    if daily_df.empty:
        st.info("暂无快照数据，收益日历暂不可用。")
        return
    _render_calendar_hover_css()

    daily_map = {
        row['day_key']: {'daily_amount': float(row['daily_amount']), 'daily_rate': float(row['daily_rate'])}
        for _, row in daily_df.iterrows()
    }

    if view_mode == 'week':
        if week_start is None:
            week_options, default_week = get_pnl_week_options(history_df, year)
            week_start = default_week if week_options else datetime.now().strftime('%Y-%m-%d')
        week_days = pd.date_range(start=week_start, periods=7, freq='D')
        metric_key = 'daily_amount' if metric_mode == 'amount' else 'daily_rate'
        values = []
        for d in week_days:
            item = daily_map.get(d.strftime('%Y-%m-%d'))
            values.append(float(item[metric_key]) if item else 0.0)
        max_abs = float(max(abs(v) for v in values)) if values else 0.0
        _render_week(week_start, daily_map, metric_mode, max_abs=max_abs, mask_value=mask_value)
        return

    if year is None:
        year = int(daily_df['date'].dt.year.max())

    year_df = daily_df[daily_df['date'].dt.year == year]
    if year_df.empty:
        st.info("该年份暂无快照数据。")
        return

    if view_mode == 'month':
        if month is None:
            month = int(year_df['date'].dt.month.max())

        scoped = year_df[year_df['date'].dt.month == month]
        metric_col = 'daily_amount' if metric_mode == 'amount' else 'daily_rate'
        max_abs = float(scoped[metric_col].abs().max()) if not scoped.empty else 0.0
        _render_month(year, month, daily_map, metric_mode, max_abs=max_abs, mask_value=mask_value)
        return

    monthly_df = _prepare_monthly_pnl(year_df)
    months_with_data = year_df['date'].dt.month.astype(int).unique().tolist()
    _render_year_cards(year, monthly_df, metric_mode, months_with_data=months_with_data, mask_value=mask_value)
