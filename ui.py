import streamlit as st  # 🔥 必须加这行，用于显示调试信息
from streamlit_echarts import st_echarts
import pandas as pd
import numpy as np      # 🔥 必须加这行，否则数学计算会报错

# 🔥 ECharts 3D 饼图 (支持隐私脱敏 mask_value)
def render_echarts_pie(df, name_col, value_col, title_text="", key=None, mask_value=False):
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