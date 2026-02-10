# 🔭 长期复利资产驾驶舱 (Compound Asset Cockpit)

> **"流水不争先，争的是滔滔不绝。"**

一个基于 Python & Streamlit 构建的个人投资管理系统，专为奉行**长期主义**、**价值投资**与**资产配置**的投资者打造。

## 📖 项目背景

在喧嚣的市场中，大多数交易软件只关注"今天涨了多少"，却忽略了"账户是否健康"。本项目不仅仅是一个记账工具，更是一个**风险控制与决策辅助系统**。

它的核心设计原则是：**健康、长久、可持续**。

通过引入宏观视角、自动汇率折算、保守估值模型以及多维度的风险看板，帮助投资者跳出短期波动的噪音，专注于资产的长期复利增长。

## 🌟 核心亮点

### 1. 🌏 宏观气候监测 (Macro Climate)

不要只低头看路，还要抬头看天。系统首屏集成全球资产定价之锚：

- **VIX 恐慌指数**：量化市场情绪。当 VIX < 15 提示"贪婪/过热"，VIX > 30 提示"恐慌/黄金坑"。
- **10年期美债收益率 (TNX)**：监控无风险利率变化，感知成长股估值压力。

### 2. 💎 真实的净资产 (True Net Assets)

- **USD 本位**：自动将港股 (HKD)、A股 (CNY) 等多币种资产，按实时汇率统一折算为美元 (USD)，反映真实购买力。
- **期权保守估值**：摒弃期权的时间价值泡沫，仅计算**内在价值 (Intrinsic Value)**。确保在极端行情下，账户净值依然"硬核"。

### 3. 🛡️ 专业的风控看板

这是本系统的灵魂所在，实时监控四大健康指标：

- **⚖️ 杠杆率 (Leverage)**：自动计算融资比例。若 > 1.2x 会亮红灯预警，防止爆仓风险。
- **🎯 集中度 (Concentration)**：Top 3 持仓占比，审视是否做到了有效聚焦。
- **🔫 干火药 (Dry Powder)**：现金/负债比例，确保手中有子弹应对暴跌。
- **📉 安全边际 (Safety Margin)**：可视化展示个股现价距离成本价的跌幅缓冲空间，越厚越从容。

### 4. 📊 交互式多维透视

引入 **ECharts** 3D 特效引擎，提供丝滑的交互体验：

- **持仓分布**：看个股权重。
- **赛道分布**：自动识别股票行业（科技、医药、消费...），防止不知不觉中的行业梭哈。
- **币种分布**：透视地缘风险敞口。
- *特效*：鼠标悬浮时扇区物理放大弹出，数据一目了然。

## 🛠️ 技术栈

| 类别 | 技术 |
|------|------|
| 前端框架 | [Streamlit](https://streamlit.io/) |
| 数据可视化 | ECharts (streamlit-echarts), Plotly Express |
| 金融数据源 | yfinance (宏观/美股), Sina Finance API (A股/港股/汇率) |
| 数据存储 | SQLite (轻量级本地数据库，数据完全隐私) |

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

依赖列表：
```
streamlit
pandas
streamlit-echarts
requests
yfinance
numpy
```

### 2. 启动应用

```bash
# 方式一：直接运行源码
streamlit run app.py

# 方式二：使用启动脚本
python run_app.py

# 方式三：使用启动脚本（关闭页面后自动空闲关停，默认120秒）
python run_app.py --idle-seconds 120
```

### 3. 访问浏览器

打开浏览器访问 http://localhost:8501

## 📁 项目结构

```
IM/
├── app.py              # 主应用入口
├── data_manager.py     # 数据库管理模块
├── utils.py            # 工具函数（价格获取、估值计算）
├── ui.py               # UI 渲染组件
├── config.py           # 配置（CSS样式、大师语录）
├── run_app.py          # 启动脚本
├── requirements.txt    # 项目依赖
├── investments.db      # SQLite 数据库（运行时生成）
├── update_price.py     # 更新股票/期权现价
├── view_db.py          # 查看数据库内容
├── daily_refresh.py    # 离线自动日更
├── scripts/
│   └── install_daily_refresh_launchd.sh  # macOS 定时任务安装
└── README.md           # 本文档
```

## 🛠️ 工具脚本

### update_price.py - 更新现价

```bash
# 查看持仓列表（排除已删除）
python3 update_price.py --list

# 更新单个股票价格
python3 update_price.py NVDA 180.00

# 批量更新价格
python3 update_price.py --batch AAPL 150 NVDA 500 MSFT 380

# 查看当前保存的价格
python3 update_price.py --prices

# 手动设定期权价格（必须用 --manual）
python3 update_price.py --manual "AMZN 2026-02-07 CALL" 8.55

# 清空所有价格数据
python3 update_price.py --reset
```

### view_db.py - 查看数据库

```bash
# 查看所有数据
python3 view_db.py

# 查看快速概览
python3 view_db.py --quick
```

### daily_refresh.py - 离线自动日更

```bash
# 手动执行一次（刷新宏观/股价并写入当日净资产快照）
python3 daily_refresh.py

# 只写快照，不刷新宏观和股价
python3 daily_refresh.py --no-macro --no-price

# 指定日期默认会被拒绝（避免伪造历史），仅限人工纠错时显式放开
python3 daily_refresh.py --date 2026-02-10 --allow-historical-snapshot
```

> 说明：这个脚本不依赖打开 Streamlit 页面，适合定时任务运行；默认只写“当天快照”。

### macOS 定时任务（launchd）

```bash
# 可选：先给脚本执行权限
chmod +x scripts/install_daily_refresh_launchd.sh

# 默认每天 20:30 自动执行
./scripts/install_daily_refresh_launchd.sh

# 自定义执行时间（示例：每天 18:05）
RUN_HOUR=18 RUN_MINUTE=5 ./scripts/install_daily_refresh_launchd.sh
```

安装后会自动生成：

- `~/Library/LaunchAgents/com.rowland.im.daily_refresh.plist`
- 日志文件：`logs/daily_refresh.out.log`、`logs/daily_refresh.err.log`

## 💾 数据库结构

### 主要表

| 表名 | 用途 | 关键字段 |
|------|------|----------|
| `transactions` | 交易记录 | symbol, type, quantity, price, asset_category |
| `fund_flows` | 资金进出 | type (DEPOSIT/WITHDRAW/RESET), amount |
| `daily_snapshots` | 每日净值 | date, total_asset, total_invested |
| `cash_balance` | 现金余额 | balance |
| `macro_cache` | 宏观数据缓存 | key (vix/tnx/cnh), value |
| `stock_meta` | 股票赛道信息 | symbol, sector, currency |
| `stock_prices` | 现价缓存 | symbol, current_price, asset_category |

### 估值优先级

```
STOCK 优先级:
  1. 实时抓取 (Sina API) → 2. stock_prices → 3. 成本价

OPTION 优先级:
  1. stock_prices (手动设定) → 2. 计算内在价值 → 3. 成本价
```

## 📝 操作指南

### 1. 添加交易

点击右下角悬浮的 ➕ 按钮，弹出操作中心：
- **股票交易**：记录股票买入/卖出
- **期权交易**：记录期权交易（自动计算 100 倍乘数）
- **本金管理**：记录入金/出金、重置本金、校准现金
- **回收站**：恢复/彻底删除误操作的交易

### 2. 查看分析

主页即看板：
- 左侧：资产分布透视（持仓/赛道/币种）
- 右侧：持仓明细表格（含市值、安全边际、持仓天数）
- 底部：财富复利曲线（$ / % 切换）

### 3. 更新期权价格

由于期权无法自动抓取价格，需要手动设定：

```bash
# 查看当前期权持仓
python3 update_price.py --list

# 手动设定期权现价
python3 update_price.py --manual "AMZN 2026-02-07 CALL" 8.55
```

## 🎖️ 勋章体系

根据持仓时间自动授予勋章：

| 持仓天数 | 勋章 | 含义 |
|----------|------|------|
| < 30 天 | 🌱 新手 | 刚入门 |
| 30-90 天 | 👀 观察员 | 观察期 |
| 90-365 天 | 🥉 坚守者 | 开始沉淀 |
| 365-1095 天 | 🥈 时间的朋友 | 一年以上 |
| 1095-1825 天 | 🥇 长期主义者 | 三年以上 |
| > 1825 天 | 💎 钻石手 | 五年以上 |

## ⚠️ 免责声明

本项目仅供个人学习与资产管理使用，不构成任何投资建议。市场有风险，投资需谨慎。

---

**Built with ❤️ for Long-Term Investors.**
