import yfinance as yf
import streamlit as st
import data_manager as db  # 引入数据库模块
import pandas as pd
from services.market_data_service import detect_currency as shared_detect_currency
from services.market_data_service import fetch_realtime_price
from services.market_data_service import get_exchange_rates as shared_get_exchange_rates


# 1. 基础工具
@st.cache_data(ttl=3600)
def get_exchange_rates():
    """获取基础汇率 (相对于 USD)"""
    return shared_get_exchange_rates()


def detect_currency(symbol):
    """代码 -> 币种"""
    return shared_detect_currency(symbol)


# 2. 价格 (必须实时)与 宏观 (可缓存)
def get_realtime_price(symbol):
    """获取股票实时价格 (Sina)"""
    return fetch_realtime_price(symbol, timeout_sec=2.0)


@st.cache_data(ttl=1800)
def get_global_macro_data():
    """
    获取全球宏观数据 (策略：优先网络，失败则读取数据库缓存)
    """
    data = {'vix': None, 'tnx': None, 'hsbfix': 20.45, 'cnh': None}

    # 辅助函数：尝试获取并缓存，失败则读库
    def fetch_and_cache(ticker, key, period="1d"):
        val = None
        try:
            # 1. 尝试联网
            hist = yf.Ticker(ticker).history(period=period)
            if not hist.empty:
                val = hist['Close'].iloc[-1]
                # 2. 存入数据库
                db.update_macro_cache(key, val)
        except:
            pass

        # 3. 如果没拿到 (网络失败), 读数据库兜底
        if val is None:
            val = db.get_macro_cache(key)
        return val

    def fetch_hsi_realized_vol_30d():
        """
        使用恒生指数 (^HSI) 计算 30 日历史波动率（年化，百分比）。
        """
        val = None
        try:
            hist = yf.Ticker("^HSI").history(period="90d")
            if not hist.empty and 'Close' in hist.columns:
                returns = hist['Close'].pct_change().dropna()
                if len(returns) >= 30:
                    window = returns.tail(30)
                    # 年化波动率（%）
                    val = float(window.std() * (252 ** 0.5) * 100)
                    db.update_macro_cache("hsbfix", val)
        except:
            pass

        if val is None:
            val = db.get_macro_cache("hsbfix")
        return val

    # 分别获取 (Yahoo Finance 比较慢，这种缓存策略非常关键)
    data['vix'] = fetch_and_cache("^VIX", "vix")
    data['tnx'] = fetch_and_cache("^TNX", "tnx")
    # 恒指波幅：改为恒生指数 30 日历史波动率（年化）
    data['hsbfix'] = fetch_hsi_realized_vol_30d()
    data['cnh'] = fetch_and_cache("CNH=X", "cnh", period="5d")

    return data


# 3. 辅助信息 (行业/期权) - 🔥 缓存加速重点
def get_stock_sector(symbol):
    """
    获取股票行业标签 (策略：优先查数据库，没有再联网)
    """
    symbol = symbol.lower().strip()

    # 1. 查数据库缓存 (速度极快)
    cached_meta = db.get_stock_meta(symbol)
    if cached_meta and cached_meta['sector']:
        return cached_meta['sector']

    # 2. 转换代码格式适配 YFinance
    yf_symbol = symbol
    if symbol.isdigit() and len(symbol) == 5:
        yf_symbol = f"{symbol}.HK"
    elif symbol.startswith('hk'):
        yf_symbol = f"{symbol[2:]}.HK"
    elif symbol.startswith('sh'):
        yf_symbol = f"{symbol[2:]}.SS"
    elif symbol.startswith('sz'):
        yf_symbol = f"{symbol[2:]}.SZ"

    sector_map = {
        'Technology': '💻 科技', 'Financial Services': '🏦 金融', 'Consumer Cyclical': '🛍️ 消费(周期)',
        'Consumer Defensive': '🛡️ 消费(防御)', 'Healthcare': '💊 医药', 'Communication Services': '📡 通信',
        'Energy': '🛢️ 能源', 'Industrials': '🏭 工业', 'Real Estate': '🏠 地产', 'Basic Materials': '🧱 原材料',
        'Utilities': '⚡ 公用事业'
    }

    sector_name = "N/A"
    try:
        ticker = yf.Ticker(yf_symbol)
        sec = ticker.info.get('sector', 'Unknown')
        sector_name = sector_map.get(sec, sec)

        # 3. 联网成功后，存入数据库
        # 注意：这里我们只存了sector，currency可以顺便存，或者留给detect_currency
        db.update_stock_meta(symbol, sector_name)

    except:
        pass

    return sector_name


def calculate_option_intrinsic_value(option_row, underlying_price):
    if underlying_price <= 0: return 0
    strike = option_row.get('strike')
    o_type = option_row.get('option_type')
    if not strike or not o_type: return 0
    if o_type == 'CALL':
        return max(0, underlying_price - strike)
    elif o_type == 'PUT':
        return max(0, strike - underlying_price)
    return 0


# 4. 估值核心逻辑
def get_stock_price_from_db(symbol, asset_category='STOCK', option_info=None):
    """从 stock_prices 表获取股票/期权现价
    
    Args:
        symbol: 股票代码
        asset_category: 资产类别 ('STOCK' 或 'OPTION')
        option_info: 期权附加信息 (dict: expiration, option_type)
    """
    prices = {}
    
    # 1. 构建可能的查找键
    search_keys = []
    
    if asset_category == 'OPTION' and option_info:
        # 构建期权代码，优先包含 strike；保留旧键兼容
        expiration = option_info.get('expiration', '')
        option_type = option_info.get('option_type', '')
        strike = option_info.get('strike', '')
        if expiration and option_type:
            option_code_with_strike = db.build_option_price_symbol(symbol, expiration, option_type, strike)
            option_code_legacy = db.build_option_price_symbol(symbol, expiration, option_type)
            search_keys.append((option_code_with_strike, 'OPTION'))
            if option_code_legacy != option_code_with_strike:
                search_keys.append((option_code_legacy, 'OPTION'))
    
    # 添加原始股票代码
    search_keys.append((symbol, asset_category))
    
    # 2. 逐一查找
    for key, cat in search_keys:
        row_price = db.get_stock_price(key)
        if row_price is not None:
            prices[key] = row_price
    
    # 3. 返回结果
    if asset_category == 'OPTION' and option_info:
        # 优先返回期权价格
        if search_keys[0][0] in prices and prices[search_keys[0][0]] is not None:
            return prices[search_keys[0][0]]
        if len(search_keys) > 1 and search_keys[1][0] in prices and prices[search_keys[1][0]] is not None:
            return prices[search_keys[1][0]]
    
    return prices.get(symbol)


def update_portfolio_valuation(df):
    rates = get_exchange_rates()
    current_prices = []
    mkt_values_usd = []
    sectors = []
    currencies = []

    for i, row in df.iterrows():
        raw_sym = row['Raw Symbol']
        currency = detect_currency(raw_sym)
        currencies.append(currency)
        rate = rates.get(currency, 1.0)

        # 准备期权信息
        option_info = None
        if row['Type'] == 'OPTION':
            option_info = {
                'expiration': str(row.get('expiration', '')) if pd.notna(row.get('expiration')) else '',
                'option_type': row.get('option_type', '') if pd.notna(row.get('option_type')) else '',
                'strike': row.get('strike', '') if pd.notna(row.get('strike')) else ''
            }

        # 1. 优先从 stock_prices 表获取价格
        db_price = get_stock_price_from_db(raw_sym, row['Type'], option_info)

        # 2. 尝试实时抓取（仅用于 STOCK）
        realtime_price = None
        if row['Type'] == 'STOCK':
            try:
                realtime_price = get_realtime_price(raw_sym)
            except:
                pass

        # 这里会利用新的缓存逻辑
        sec = get_stock_sector(raw_sym) if row['Type'] == 'STOCK' else "📜 期权"
        sectors.append(sec)

        final_price_native = 0
        if row['Type'] == 'STOCK':
            # STOCK: 优先实时抓取，其次用 stock_prices，最后用成本价
            final_price_native = (
                realtime_price
                if realtime_price is not None
                else (db_price if db_price is not None else (row['Avg Cost'] or 0))
            )
        elif row['Type'] == 'OPTION':
            # OPTION: 只使用手动设定价格；不抓取/不推算，避免 0 覆盖
            final_price_native = db_price if db_price is not None else (row['Avg Cost'] or 0)

        val_usd = final_price_native * row['Quantity'] * row['Multiplier'] * rate
        current_prices.append(final_price_native)
        mkt_values_usd.append(val_usd)

    df['Price'] = current_prices
    df['Market Value'] = mkt_values_usd
    df['Sector'] = sectors
    df['Currency'] = currencies
    return df


# 5. 勋章逻辑
def get_badge_info(days):
    if days >= 1825: return "💎", "钻石手"
    if days >= 1095: return "🥇", "长期主义者"
    if days >= 365:  return "🥈", "时间的朋友"
    if days >= 90:   return "🥉", "坚守者"
    if days >= 30:   return "👀", "观察员"
    return "🌱", "新手"
