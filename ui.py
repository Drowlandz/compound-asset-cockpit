import streamlit as st  # 🔥 必须加这行，用于显示调试信息
from streamlit_echarts import st_echarts
import pandas as pd
import numpy as np      # 🔥 必须加这行，否则数学计算会报错

# 🔥 ECharts 3D 饼图 (修复版：右下角图例按占比从大到小排序)
def render_echarts_pie(df, name_col, value_col, title_text="", key=None):
    # 🔥 1. 核心修改：按金额/占比从大到小排序
    df_sorted = df.sort_values(by=value_col, ascending=False)

    # 2. 计算总资产
    total_val = df_sorted[value_col].astype(float).sum()

    # 3. 生成数据列表 (此时数据已经是排好序的)
    data_list = []
    for _, row in df_sorted.iterrows():
        val = float(row[value_col])
        pct = (val / total_val * 100) if total_val > 0 else 0
        # 补齐空格保持视觉对齐 (可选)
        name_with_pct = f"{str(row[name_col])}  {pct:.1f}%"
        data_list.append({"value": val, "name": name_with_pct})

    options = {
        "tooltip": {"trigger": "item", "formatter": "{b}: ${c}"},

        # 图例设置：右下角垂直排列，自然继承数据的排序
        "legend": {
            "show": True,
            "orient": "vertical",
            "right": "2%",
            "bottom": "5%",
            "itemGap": 10,
            "textStyle": {"fontSize": 12, "color": "#475569", "fontWeight": "bold"}
        },

        "series": [{
            "name": title_text,
            "type": "pie",
            "radius": ["45%", "75%"],
            "center": ["35%", "50%"],  # 饼图靠左，给排序图例留空间
            "itemStyle": {"borderRadius": 8, "borderColor": "#fff", "borderWidth": 2},
            "label": {"show": False},
            "emphasis": {
                "label": {
                    "show": True,
                    "fontSize": 16,
                    "fontWeight": "bold",
                    "formatter": "{b}",
                    "color": "#333"
                },
                "scale": True, "scaleSize": 15,
                "itemStyle": {"shadowBlur": 20, "shadowOffsetX": 0, "shadowColor": "rgba(0, 0, 0, 0.2)"}
            },
            "data": data_list
        }]
    }

    st_echarts(options=options, height="280px", key=key)


# ui.py (全量替换 render_history_chart 函数)

def render_history_chart(history_df, mode='value'):
    """
    稳健版：移除复杂特效，强制显示数据点，确保图表 100% 能显示。
    """
    if history_df is None or history_df.empty:
        return

    # 1. 数据清洗 (保持最稳健的逻辑)
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

        options = {
            "tooltip": {
                "trigger": 'axis',
                "backgroundColor": "rgba(255,255,255,0.95)",
                "textStyle": {"color": "#333"},
                "formatter": "<b>📅 {b}</b><br/>💰 净资产: <b>${c0}</b><br/>🏦 总本金: <b>${c1}</b>"
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
                "axisLabel": {"formatter": "${value}", "color": "#94a3b8"}
            },
            "series": [
                {
                    "name": "净资产",
                    "type": "line",
                    "smooth": 0.2,
                    "showSymbol": True,  # 🔥 强制显示点
                    "symbolSize": 6,
                    "lineStyle": {"width": 3, "color": "#16a34a"},  # 绿色实线
                    "itemStyle": {"color": "#16a34a"},
                    "data": assets
                },
                {
                    "name": "总本金",
                    "type": "line",
                    "smooth": 0.2,
                    "showSymbol": False,
                    "lineStyle": {"width": 2, "color": "#94a3b8", "type": "dashed"},  # 灰色虚线
                    "itemStyle": {"color": "#94a3b8"},
                    "data": principals
                }
            ]
        }

    # ================= 模式 B: 收益率百分比 (%) =================
    else:
        yields = []
        for i, row in df.iterrows():
            inv = float(row['total_invested'])
            ass = float(row['total_asset'])

            # 收益率计算
            val = 0.0
            if inv > 1.0:
                val = (ass - inv) / inv * 100.0

            # 过滤异常值
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
            # 🔥 移除 visualMap，改用单一颜色，确保能显示！
            "series": [{
                "name": '累计收益率',
                "type": 'line',
                "smooth": 0.2,
                "showSymbol": True,  # 🔥 强制显示点
                "symbolSize": 6,
                "lineStyle": {"width": 3, "color": "#ea580c"},  # 使用醒目的橙红色
                "itemStyle": {"color": "#ea580c"},
                "markLine": {
                    "symbol": "none",
                    "data": [{"yAxis": 0}],
                    "label": {"show": True, "position": "end", "formatter": "0%", "color": "#94a3b8"},
                    "lineStyle": {"color": "#64748b", "type": "solid", "width": 1}
                },
                "areaStyle": {
                    "opacity": 0.1,
                    "color": "#ea580c"  # 单色背景
                },
                "data": yields
            }]
        }

    # 渲染图表
    st_echarts(options=options, height="350px", key=f"chart_history_{mode}")