# ui.py
from streamlit_echarts import st_echarts
import pandas as pd


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