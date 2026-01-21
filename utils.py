import requests
import yfinance as yf
import streamlit as st
import data_manager as db  # 引入数据库模块


# 1. 基础工具
@st.cache_data(ttl=3600)
def get_exchange_rates():
    """获取基础汇率 (相对于 USD)"""
    return {'USD': 1.0, 'HKD': 0.128, 'CNY': 0.138, 'CNH': 0.138}


def detect_currency(symbol):
    """代码 -> 币种"""
    symbol = symbol.lower().strip()
    if symbol.isdigit() and len(symbol) == 5: return 'HKD'
    if symbol.startswith('hk'): return 'HKD'
    if symbol.startswith('sh') or symbol.startswith('sz') or (symbol.isdigit() and len(symbol) == 6): return 'CNY'
    return 'USD'


# 2. 价格 (必须实时)与 宏观 (可缓存)
def get_realtime_price(symbol):
    """获取股票实时价格 (Sina)"""
    symbol = symbol.lower().strip()
    headers = {'Referer': 'https://finance.sina.com.cn'}
    try:
        if ' ' in symbol: return None
        if symbol.isalpha():  # 美股
            url = f"https://hq.sinajs.cn/list=gb_{symbol}"
            resp = requests.get(url, headers=headers, timeout=2)
            content = resp.text.split('="')[1].split(',')
            if len(content) > 1: return float(content[1])
        else:  # A股/港股
            if not (symbol.startswith('sh') or symbol.startswith('sz') or symbol.startswith('hk')):
                if len(symbol) == 5:
                    prefix = 'hk'
                else:
                    prefix = 'sh' if symbol.startswith('6') else 'sz'
                symbol = prefix + symbol
            url = f"https://hq.sinajs.cn/list={symbol}"
            resp = requests.get(url, headers=headers, timeout=2)
            content = resp.text.split('="')[1].split(',')
            if len(content) > 3: return float(content[6] if 'hk' in symbol else content[3])
    except:
        return None
    return None


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

    # 分别获取 (Yahoo Finance 比较慢，这种缓存策略非常关键)
    data['vix'] = fetch_and_cache("^VIX", "vix")
    data['tnx'] = fetch_and_cache("^TNX", "tnx")
    data['vhsi'] = fetch_and_cache("^VHSI", "vhsi", period="5d")
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

        price = get_realtime_price(raw_sym)

        # 这里会利用新的缓存逻辑
        sec = get_stock_sector(raw_sym) if row['Type'] == 'STOCK' else "📜 期权"
        sectors.append(sec)

        final_price_native = 0
        if row['Type'] == 'STOCK':
            final_price_native = price if price else (row['Avg Cost'] or 0)
        elif row['Type'] == 'OPTION':
            final_price_native = calculate_option_intrinsic_value(row, price) if price else (row['Avg Cost'] or 0)

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