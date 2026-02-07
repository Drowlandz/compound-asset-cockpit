# config.py
import random

# ================= CSS 样式表 =================
CUSTOM_CSS = """
<style>
    /* 全局基础 */
    html, body, [class*="css"] { font-family: 'Check', -apple-system, system-ui, sans-serif; }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    section[data-testid="stSidebar"] { display: none; }

    /* 2. 隐藏 Streamlit 默认的 Radio 圆圈，改为胶囊按钮 */
    div[data-testid="stRadio"] > label {
        display: none !important; /* 隐藏 Label 文字（如果有） */
    }
    
    /* 容器背景 (灰色底槽) */
    div[data-testid="stRadio"] > div[role="radiogroup"] {
        background-color: #f1f5f9; /* Slate-100 */
        padding: 4px;
        border-radius: 8px;
        display: inline-flex;
        width: auto;
        gap: 0px; /* 紧挨着 */
    }

    /* 每一个选项 (默认状态) */
    div[data-testid="stRadio"] label[data-baseweb="radio"] {
        background-color: transparent;
        border: none;
        margin: 0 !important;
        padding: 4px 16px !important; /* 紧凑 Padding */
        border-radius: 6px;
        transition: all 0.2s ease;
        cursor: pointer;
    }
    
    /* 隐藏原生 Input 圆圈 */
    div[data-testid="stRadio"] label[data-baseweb="radio"] > div:first-child {
        display: none; 
    }
    
    /* 文字样式 */
    div[data-testid="stRadio"] label[data-baseweb="radio"] > div {
        color: #64748b; /* Slate-500 */
        font-weight: 500;
        font-size: 14px;
    }

    /* 🔥 选中状态 (利用 :has 选择器实现阴影卡片效果) */
    div[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) {
        background-color: #ffffff;
        box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px -1px rgba(0, 0, 0, 0.1); /* 阴影 */
        color: #0f172a;
    }
    
    /* 选中状态的文字颜色 */
    div[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) > div {
        color: #0f172a !important; /* Slate-900 */
        font-weight: 600;
    }

    /* === 2. 荣誉勋章 (右上角悬浮 + 呼吸灯) === */
    @keyframes breathe {
        0% { box-shadow: 0 0 5px rgba(255, 215, 0, 0.3); transform: scale(1); }
        50% { box-shadow: 0 0 15px rgba(255, 215, 0, 0.6); transform: scale(1.02); }
        100% { box-shadow: 0 0 5px rgba(255, 215, 0, 0.3); transform: scale(1); }
    }
    .badge-container {
        position: fixed; top: 60px; right: 30px; z-index: 9999;
        background: rgba(255, 255, 255, 0.95); backdrop-filter: blur(5px);
        border: 1px solid #eab308; border-left: 6px solid #eab308;
        border-radius: 8px; padding: 8px 16px;
        display: flex; align-items: center; gap: 12px;
        box-shadow: 0 10px 25px rgba(234, 179, 8, 0.15);
        animation: breathe 4s infinite ease-in-out;
        transition: transform 0.3s;
    }
    .badge-container:hover { transform: translateY(-2px); }
    .badge-icon { font-size: 28px; filter: drop-shadow(0 2px 2px rgba(0,0,0,0.1)); }
    .badge-text { font-family: 'Segoe UI', sans-serif; font-weight: 800; color: #854d0e; font-size: 15px; line-height: 1.1; }
    .badge-label { font-size: 11px; color: #a16207; font-weight: 500; margin-top: 2px; }

    /* === 3. 卡片与布局优化 === */
    /* 语录卡片 */
    .quote-card {
        background: linear-gradient(to right, #f8f9fa, #fff);
        border-left: 4px solid #3b82f6;
        padding: 12px 20px;
        margin-bottom: 25px;
        border-radius: 0 8px 8px 0;
        font-family: 'Georgia', serif;
        font-style: italic;
        color: #374151;
        font-size: 16px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.02);
    }
    .quote-author { text-align: right; font-weight: 600; font-size: 13px; color: #9ca3af; margin-top: 4px; font-style: normal; }

    /* 核心指标卡片 */
    div[data-testid="stMetric"] {
        background-color: #ffffff; padding: 18px 24px; border-radius: 16px;
        border: 1px solid #f1f5f9; 
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.01), 0 2px 4px -1px rgba(0, 0, 0, 0.01);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }
    div[data-testid="stMetric"]:hover {
        transform: translateY(-5px);
        box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.05), 0 10px 10px -5px rgba(0, 0, 0, 0.01);
        border-color: #cbd5e1;
    }
    div[data-testid="column"]:nth-child(1) div[data-testid="stMetric"] label { font-size: 13px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; color: #64748b; }

    /* 净资产卡片 (极光绿渐变) */
    div.net-asset-card div[data-testid="stMetric"] {
        background: linear-gradient(120deg, #ffffff 0%, #ecfdf5 100%);
        border: 1px solid #a7f3d0;
        border-left: 6px solid #059669;
    }

    /* 悬浮按钮 */
    div.stButton:has(button:active), div.stButton:last-of-type {
        position: fixed; bottom: 40px; right: 40px; z-index: 9999; width: auto;
    }
    div.stButton:last-of-type > button {
        border-radius: 50%; width: 64px; height: 64px; font-size: 28px;
        background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
        color: white; box-shadow: 0 10px 25px rgba(220, 38, 38, 0.4); 
        border: 2px solid #fff;
        transition: transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1);
    }
    div.stButton:last-of-type > button:hover { transform: scale(1.15) rotate(90deg); box-shadow: 0 15px 35px rgba(220, 38, 38, 0.5); }

    /* 修正弹窗按钮 */
    div[data-testid="stDialog"] div.stButton { position: static !important; width: auto !important; }
    div[data-testid="stDialog"] button { border-radius: 6px !important; width: auto !important; height: auto !important; font-size: 1rem !important; background: #f1f5f9; color: #0f172a; border: 1px solid #cbd5e1; box-shadow: none; }
    div[data-testid="stDialog"] button:hover { background: #e2e8f0; }
</style>
"""

# ================= 大师语录库 =================
QUOTES_LIST = [
    ("流水不争先，争的是滔滔不绝。", "道德经"),
    ("价格是你付出的，价值是你得到的。", "沃伦·巴菲特"),
    ("短期看，市场是投票机；长期看，市场是称重机。", "本杰明·格雷厄姆"),
    ("投资的本质是认知变现。", "查理·芒格"),
    ("不要亏损。不要亏损。不要亏损。", "沃伦·巴菲特"),
    ("如果你不能在睡觉时也赚钱，你就会工作到死。", "沃伦·巴菲特"),
    ("巨大的财富不是靠买卖赚来的，而是靠等待赚来的。", "查理·芒格"),
    ("如果你手里有一把锤子，所有东西看起来都像钉子。", "查理·芒格"),
    ("你要寻找的是那些你想拥有十年的公司，而不是你想持有十分钟的股票。", "沃伦·巴菲特"),
    ("只有退潮时，你才知道谁在裸泳。", "沃伦·巴菲特"),
    ("在这行，最昂贵的四个字是：这次不一样。", "约翰·坦普顿"),
    ("别人贪婪我恐惧，别人恐惧我贪婪。", "沃伦·巴菲特"),
    ("复利是世界第八大奇迹。", "阿尔伯特·爱因斯坦"),
    ("即使你拥有全世界最优秀的企业，如果你买入的价格太高，依然是一笔糟糕的投资。", "霍华德·马克斯"),
    ("大多数人高估了他们一年能做的事情，而低估了他们十年能做的事情。", "比尔·盖茨"),
    ("不要试图预测风雨，要学会建造方舟。", "投资谚语"),
    ("慢就是顺，顺就是快。", "海豹突击队格言"),
    ("大智若愚，大巧若拙。", "道德经"),
    ("反过来想，总是反过来想。", "查理·芒格"),
    ("如果你的生活方式是正确的，那么你不需要变得富有。", "查理·芒格"),
    ("所有巨大的财富都来自于长期的持有。", "菲利普·费雪"),
    ("买入一家伟大的公司并一直持有，比买入一家平庸的公司并试图在它身上赚钱要容易得多。", "沃伦·巴菲特"),
    ("风险来自你不知道自己在做什么。", "沃伦·巴菲特"),
    ("如果你在打扑克牌时，20分钟还看不出谁是傻瓜，那你就是那个傻瓜。", "沃伦·巴菲特"),
    ("不需要太聪明，只要不犯傻就行。", "查理·芒格"),
    ("悲观者正确，乐观者赚钱。", "投资谚语"),
    ("耐心是投资中最重要的美德。", "彼得·林奇"),
    ("在市场中，情绪是最大的敌人。", "本杰明·格雷厄姆"),
    ("不要把鸡蛋放在一个篮子里，但也不要放在太多的篮子里。", "投资谚语"),
    ("长期投资不仅是一种策略，更是一种生活态度。", "佚名"),
    ("财富是耐心的报酬。", "佚名"),
    ("知人者智，自知者明。", "道德经"),
    ("静水流深。", "中国谚语"),
    ("欲速则不达。", "论语"),
    ("风物长宜放眼量。", "毛泽东"),
    ("每临大事有静气。", "翁同龢"),
    ("兵无常势，水无常形。", "孙子兵法"),
    ("善战者，无智名，无勇功。", "孙子兵法"),
    ("守正出奇。", "孙子兵法"),
    # 但斌经典语录
    ("在中国做投资，不需要你很聪明，但需要你能够坚持。", "但斌"),
    ("投资是一场马拉松，不是百米冲刺。", "但斌"),
    ("伟大是熬出来的。", "但斌"),
    ("时间是优秀企业的朋友，是平庸企业的敌人。", "但斌"),
    ("投资最困难的是当别人恐惧时要贪婪，在别人贪婪时恐惧。", "但斌")
]


def get_random_quote():
    return random.choice(QUOTES_LIST)