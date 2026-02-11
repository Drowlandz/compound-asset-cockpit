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
    .badge-container:hover { transform: translateY(-2px) scale(1.05); }
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
    /* 健康/风险状态悬浮边框 */
    .st-key-lev_metric_ok div[data-testid="stMetric"]:hover,
    .st-key-conc_metric_ok div[data-testid="stMetric"]:hover,
    .st-key-cash_metric_wrap div[data-testid="stMetric"]:hover,
    .st-key-cash_flat_metric_wrap div[data-testid="stMetric"]:hover,
    .st-key-profit_metric_ok div[data-testid="stMetric"]:hover {
        border-color: #16a34a;
        box-shadow: 0 20px 25px -5px rgba(22, 163, 74, 0.22), 0 10px 10px -5px rgba(22, 163, 74, 0.12);
    }
    .st-key-lev_metric_bad div[data-testid="stMetric"]:hover,
    .st-key-conc_metric_bad div[data-testid="stMetric"]:hover,
    .st-key-debt_metric_wrap div[data-testid="stMetric"]:hover,
    .st-key-profit_metric_bad div[data-testid="stMetric"]:hover {
        border-color: #dc2626;
        box-shadow: 0 20px 25px -5px rgba(220, 38, 38, 0.24), 0 10px 10px -5px rgba(220, 38, 38, 0.12);
    }
    div[data-testid="column"]:nth-child(1) div[data-testid="stMetric"] label { font-size: 13px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; color: #64748b; }

    /* 净资产卡片 (极光绿渐变) */
    div.net-asset-card div[data-testid="stMetric"] {
        background: linear-gradient(120deg, #ffffff 0%, #ecfdf5 100%);
        border: 1px solid #a7f3d0;
        border-left: 6px solid #059669;
    }

    /* 持仓市值卡片 (清爽蓝渐变) */
    div.holding-asset-card div[data-testid="stMetric"] {
        background: linear-gradient(120deg, #ffffff 0%, #eff6ff 100%);
        border: 1px solid #bfdbfe;
        border-left: 6px solid #2563eb;
    }

    /* 现金/负债状态卡片 */
    div.cash-asset-card div[data-testid="stMetric"] {
        background: linear-gradient(120deg, #ffffff 0%, #ecfdf5 100%);
        border: 1px solid #bbf7d0;
        border-left: 6px solid #16a34a;
    }
    div.debt-asset-card div[data-testid="stMetric"] {
        background: linear-gradient(120deg, #ffffff 0%, #fef2f2 100%);
        border: 1px solid #fecaca;
        border-left: 6px solid #dc2626;
    }
    div.cash-flat-card div[data-testid="stMetric"] {
        background: linear-gradient(120deg, #ffffff 0%, #f8fafc 100%);
        border: 1px solid #e2e8f0;
        border-left: 6px solid #64748b;
    }
    .st-key-cash_metric_wrap div[data-testid="stMetric"] {
        background: linear-gradient(120deg, #ffffff 0%, #ecfdf5 100%);
        border: 1px solid #bbf7d0;
        border-left: 6px solid #16a34a;
    }
    .st-key-debt_metric_low_wrap div[data-testid="stMetric"] {
        background: linear-gradient(120deg, #ffffff 0%, #fff7ed 100%);
        border: 1px solid #fed7aa;
        border-left: 6px solid #f59e0b;
    }
    .st-key-debt_metric_mid_wrap div[data-testid="stMetric"] {
        background: linear-gradient(120deg, #ffffff 0%, #ffedd5 100%);
        border: 1px solid #fdba74;
        border-left: 6px solid #f97316;
    }
    .st-key-debt_metric_high_wrap div[data-testid="stMetric"] {
        background: linear-gradient(120deg, #ffffff 0%, #fef2f2 100%);
        border: 1px solid #fecaca;
        border-left: 6px solid #dc2626;
    }
    .st-key-cash_flat_metric_wrap div[data-testid="stMetric"] {
        background: linear-gradient(120deg, #ffffff 0%, #f8fafc 100%);
        border: 1px solid #e2e8f0;
        border-left: 6px solid #64748b;
    }

    /* 悬浮按钮（仅绑定 fab 容器，避免误伤其他按钮） */
    .st-key-fab_wrap div[data-testid="stButton"] {
        position: fixed;
        bottom: 40px;
        right: 40px;
        z-index: 9999;
        width: auto;
    }
    .st-key-fab_wrap div[data-testid="stButton"] > button {
        border-radius: 50%; width: 64px; height: 64px; font-size: 28px;
        background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
        color: white; box-shadow: 0 10px 25px rgba(220, 38, 38, 0.4); 
        border: 2px solid #fff;
        transition: transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1);
    }
    .st-key-fab_wrap div[data-testid="stButton"] > button:hover {
        transform: scale(1.15) rotate(90deg);
        box-shadow: 0 15px 35px rgba(220, 38, 38, 0.5);
    }

    /* 操作中心弹窗（克制风格） */
    div[data-testid="stDialog"] div[role="dialog"] {
        max-width: 920px !important;
        width: min(920px, 94vw) !important;
        border-radius: 16px !important;
        border: 1px solid #e2e8f0 !important;
        background: #ffffff !important;
        box-shadow: 0 20px 45px -18px rgba(15, 23, 42, 0.35) !important;
    }
    div[data-testid="stDialog"] div.stButton { position: static !important; width: auto !important; }
    div[data-testid="stDialog"] [data-baseweb="tab-list"] {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        padding: 8px;
        gap: 12px;
        margin-bottom: 12px;
    }
    div[data-testid="stDialog"] button[role="tab"] {
        height: 38px;
        border: 1px solid #e2e8f0 !important;
        border-radius: 10px;
        background: #f8fafc !important;
        color: #64748b !important;
        font-weight: 600;
        font-size: 13px;
        padding: 0 14px;
        transition: all 0.15s ease;
    }
    div[data-testid="stDialog"] button[role="tab"]:hover {
        background: #eef2ff !important;
        border-color: #cbd5e1 !important;
        color: #334155 !important;
    }
    div[data-testid="stDialog"] button[role="tab"][aria-selected="true"] {
        background: #dbeafe !important;
        border-color: #93c5fd !important;
        color: #1e3a8a !important;
        box-shadow: 0 2px 8px rgba(59, 130, 246, 0.15);
    }
    /* 覆盖全局 radio，给弹窗里的分段选择更紧凑的样式 */
    div[data-testid="stDialog"] div[data-testid="stRadio"] > div[role="radiogroup"] {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 3px;
        gap: 2px;
    }
    div[data-testid="stDialog"] div[data-testid="stRadio"] label[data-baseweb="radio"] {
        padding: 5px 12px !important;
        border-radius: 8px;
    }
    div[data-testid="stDialog"] div[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) {
        background: #ffffff;
        border: 1px solid #cbd5e1;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.08);
    }
    div[data-testid="stDialog"] div[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) > div {
        color: #0f172a !important;
        font-weight: 700;
    }
    div[data-testid="stDialog"] [data-baseweb="input"] {
        border-radius: 10px;
        border: 1px solid #cbd5e1;
        background: #fff;
        transition: all 0.15s ease;
    }
    div[data-testid="stDialog"] [data-baseweb="input"]:focus-within {
        border-color: #2563eb;
        box-shadow: 0 0 0 3px #dbeafe;
    }
    div[data-testid="stDialog"] [data-baseweb="select"] > div {
        border-radius: 10px;
        border: 1px solid #cbd5e1;
        min-height: 40px;
    }
    /* 弹窗内多列字段间距收紧，避免空白断裂 */
    div[data-testid="stDialog"] div[data-testid="stHorizontalBlock"] {
        gap: 0.75rem;
    }
    div[data-testid="stDialog"] div.stButton > button {
        width: auto !important;
        min-height: 36px !important;
        height: 36px !important;
        border-radius: 9px !important;
        border: 1px solid #cbd5e1 !important;
        background: #f8fafc !important;
        color: #0f172a !important;
        font-weight: 700;
        padding: 0 12px !important;
        box-shadow: none !important;
        transform: none !important;
        transition: background-color 0.15s ease, border-color 0.15s ease, color 0.15s ease !important;
    }
    div[data-testid="stDialog"] div.stButton > button:hover {
        border-color: #94a3b8 !important;
        background: #f1f5f9 !important;
        transform: none !important;
        box-shadow: none !important;
    }
    div[data-testid="stDialog"] div.stButton > button[data-testid="baseButton-primary"] {
        border: 1px solid #1d4ed8 !important;
        background: #2563eb !important;
        color: #ffffff !important;
    }
    div[data-testid="stDialog"] div.stButton > button[data-testid="baseButton-primary"]:hover {
        background: #1d4ed8 !important;
        border-color: #1e40af !important;
    }
    div[data-testid="stDialog"] div.stButton > button[data-testid="baseButton-secondary"] {
        border: 1px solid #86efac !important;
        background: #ecfdf5 !important;
        color: #166534 !important;
    }
    div[data-testid="stDialog"] div.stButton > button[data-testid="baseButton-secondary"]:hover {
        border-color: #4ade80 !important;
        background: #dcfce7 !important;
        color: #14532d !important;
    }
    @media (max-width: 768px) {
        div[data-testid="stDialog"] div[role="dialog"] {
            width: 96vw !important;
        }
    }
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
    ("投资最困难的是当别人恐惧时要贪婪，在别人贪婪时恐惧。", "但斌"),
    # 查理·芒格精选
    ("我只想知道我将来会死在哪里，这样我就永远不去那里。", "查理·芒格"),
    ("要得到你想要的东西，最可靠的方法是让自己配得上它。", "查理·芒格"),
    ("如果你只是重复和别人一样的事，你很难比别人做得更好。", "查理·芒格"),
    ("避免愚蠢，比追求聪明更容易让你长期胜出。", "查理·芒格"),
    ("好机会来临时，要有勇气下重注。", "查理·芒格"),
    ("大部分人不愿意把事情想清楚，这就是机会。", "查理·芒格"),
    ("持续学习是长期竞争力的核心。", "查理·芒格"),
    ("耐心和纪律，是投资里最被低估的优势。", "查理·芒格"),
    ("你不需要每次都挥棒，只需要等到你的甜蜜点。", "查理·芒格"),
    ("正确的长期行为，短期看起来常常不舒服。", "查理·芒格"),
    ("如果一个决定需要很多假设才成立，通常它就不够好。", "查理·芒格"),
    ("简单、可重复、可验证的系统，优于复杂且脆弱的系统。", "查理·芒格"),
    ("你真正该害怕的不是波动，而是永久性损失。", "查理·芒格"),
    ("当你不知道该做什么时，先别做。", "查理·芒格"),
    ("把注意力放在少数高质量机会，而不是频繁动作。", "查理·芒格"),
    ("第一条规则是别欺骗自己，而你最容易欺骗的人就是自己。", "查理·芒格"),
    ("嫉妒是最愚蠢的情绪，因为它不会给你任何回报。", "查理·芒格"),
    ("如果你不在能力圈内行动，迟早会交学费。", "查理·芒格"),
    ("优秀的结果来自长期做对的事，而不是偶尔做对一次。", "查理·芒格"),
    # 其他补充
    ("波动不是风险，永久亏损才是风险。", "霍华德·马克斯"),
    ("成功的投资不在于避免错误，而在于避免致命错误。", "雷·达里奥"),
    ("真正的护城河来自企业持续创造现金流的能力。", "投资箴言"),
    ("在不确定性中，仓位管理比预测更重要。", "投资箴言"),
    ("你可以错很多次，只要每次亏得不大。", "乔治·索罗斯")
]


def get_random_quote():
    return random.choice(QUOTES_LIST)
