#!/usr/bin/env python3
"""
IM 告警系统
监控持仓风险指标，根据阈值发出告警
"""

import sys
import os
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import data_manager as db
import utils as ut
import pandas as pd


class AlertLevel:
    INFO = "INFO"      # 信息
    WARNING = "WARNING" # 警告
    CRITICAL = "CRITICAL" # 严重


class Alert:
    def __init__(self, level, title, message, action=None):
        self.level = level
        self.title = title
        self.message = message
        self.action = action
        self.timestamp = datetime.now()
        
    def __str__(self):
        emoji = {
            "INFO": "ℹ️",
            "WARNING": "⚠️",
            "CRITICAL": "🚨"
        }.get(self.level, "❓")
        
        return f"{emoji} **[{self.level}]** {self.title}\n   {self.message}"


class AlertSystem:
    def __init__(self):
        self.alerts = []
        
    def check_concentration(self, portfolio_df):
        """检查集中度告警"""
        if portfolio_df.empty:
            return
            
        market_val = portfolio_df['Market Value'].sum()
        if market_val == 0:
            return
            
        # Top 3 集中度
        top3 = portfolio_df.nlargest(3, 'Market Value')['Market Value'].sum()
        concentration = (top3 / market_val * 100)
        
        if concentration < 60:
            self.alerts.append(Alert(
                AlertLevel.CRITICAL,
                "集中度过低（<60%）",
                f"Top3 集中度仅 {concentration:.1f}%，过度分散可能导致收益被稀释",
                action="考虑增加持仓集中度，聚焦核心标的"
            ))
        elif concentration < 70:
            self.alerts.append(Alert(
                AlertLevel.WARNING,
                "集中度偏低（60-70%）",
                f"Top3 集中度 {concentration:.1f}%，略低于理想水平",
                action="可适度提高核心持仓占比"
            ))
        elif concentration < 80:
            self.alerts.append(Alert(
                AlertLevel.INFO,
                "集中度接近阈值（70-80%）",
                f"Top3 集中度 {concentration:.1f}%，接近 80% 阈值",
                action="密切关注，保持当前策略"
            ))
        # 集中度 >= 80% 为正常，不告警
        
    def check_cash(self, cash, net_asset):
        """检查现金流告警"""
        if cash >= 0:
            return
            
        cash_ratio = abs(cash) / net_asset * 100 if net_asset > 0 else 0
        
        if cash_ratio > 30:
            self.alerts.append(Alert(
                AlertLevel.CRITICAL,
                "现金流严重为负（>30%）",
                f"现金为 ${cash:,.0f}，占净资产 {cash_ratio:.1f}%",
                action="立即减仓，降低杠杆"
            ))
        elif cash_ratio > 20:
            self.alerts.append(Alert(
                AlertLevel.WARNING,
                "现金流为负（20-30%）",
                f"现金为 ${cash:,.0f}，占净资产 {cash_ratio:.1f}%",
                action="关注杠杆风险，准备减仓"
            ))
        elif cash_ratio > 10:
            self.alerts.append(Alert(
                AlertLevel.INFO,
                "现金流为负（10-20%）",
                f"现金为 ${cash:,.0f}，占净资产 {cash_ratio:.1f}%",
                action="保持警惕，监控变化"
            ))
            
    def check_leverage(self, market_val, net_asset):
        """检查杠杆率告警"""
        if net_asset <= 0:
            return
            
        leverage = market_val / net_asset
        
        if leverage > 2.0:
            self.alerts.append(Alert(
                AlertLevel.CRITICAL,
                "杠杆率过高（>2.0x）",
                f"当前杠杆率 {leverage:.2f}x，风险极大",
                action="立即减仓，降低杠杆"
            ))
        elif leverage > 1.5:
            self.alerts.append(Alert(
                AlertLevel.WARNING,
                "杠杆率偏高（1.5-2.0x）",
                f"当前杠杆率 {leverage:.2f}x",
                action="关注融资成本，准备调整"
            ))
        elif leverage > 1.2:
            self.alerts.append(Alert(
                AlertLevel.INFO,
                "杠杆率略高（1.2-1.5x）",
                f"当前杠杆率 {leverage:.2f}x",
                action="保持监控"
            ))
            
    def check_sector_concentration(self, portfolio_df):
        """检查赛道集中度告警"""
        if portfolio_df.empty:
            return
            
        market_val = portfolio_df['Market Value'].sum()
        if market_val == 0:
            return
            
        sector_df = portfolio_df.groupby('Sector')['Market Value'].sum()
        total = sector_df.sum()
        
        for sector, val in sector_df.items():
            pct = (val / total * 100) if total > 0 else 0
            
            if pct > 80:
                self.alerts.append(Alert(
                    AlertLevel.CRITICAL,
                    f"赛道过度集中（{sector} > 80%）",
                    f"{sector} 占比 {pct:.1f}%",
                    action="立即分散配置，降低单一赛道风险"
                ))
            elif pct > 70:
                self.alerts.append(Alert(
                    AlertLevel.WARNING,
                    f"赛道集中度高（{sector} 70-80%）",
                    f"{sector} 占比 {pct:.1f}%",
                    action="关注赛道风险，考虑适度分散"
                ))
            elif pct > 60:
                self.alerts.append(Alert(
                    AlertLevel.INFO,
                    f"赛道占比较高（{sector} 60-70%）",
                    f"{sector} 占比 {pct:.1f}%",
                    action="保持关注"
                ))
                
    def check_loss_ratio(self, portfolio_df):
        """检查亏损比例告警"""
        if portfolio_df.empty:
            return
            
        portfolio_df['PnL $'] = portfolio_df['Market Value'] - portfolio_df['Total Cost']
        
        gainers = len(portfolio_df[portfolio_df['PnL $'] > 0])
        losers = len(portfolio_df[portfolio_df['PnL $'] < 0])
        total = len(portfolio_df)
        
        if total == 0:
            return
            
        loss_ratio = losers / total * 100
        
        if loss_ratio > 50:
            self.alerts.append(Alert(
                AlertLevel.WARNING,
                "亏损持仓过半",
                f"{losers}/{total} 只持仓亏损（{loss_ratio:.0f}%）",
                action="审视亏损持仓，考虑止损"
            ))
            
    def check_max_drawdown_risk(self, portfolio_df):
        """检查最大回撤风险"""
        if portfolio_df.empty:
            return
            
        portfolio_df['PnL $'] = portfolio_df['Market Value'] - portfolio_df['Total Cost']
        portfolio_df['Return %'] = (portfolio_df['PnL $'] / portfolio_df['Total Cost'] * 100)
        
        losers = portfolio_df[portfolio_df['Return %'] < -20]
        
        if len(losers) > 0:
            for _, row in losers.iterrows():
                if row['Return %'] < -30:
                    self.alerts.append(Alert(
                        AlertLevel.CRITICAL,
                        f"{row['Symbol']} 严重亏损（>{-30}%）",
                        f"{row['Symbol']} 亏损 {row['Return %']:.1f}%",
                        action="立即评估，考虑止损"
                    ))
                elif row['Return %'] < -20:
                    self.alerts.append(Alert(
                        AlertLevel.WARNING,
                        f"{row['Symbol']} 亏损较大（>-30%）",
                        f"{row['Symbol']} 亏损 {row['Return %']:.1f}%",
                        action="密切关注，准备止损"
                    ))
                    
    def run_all_checks(self):
        """运行所有检查"""
        self.alerts = []
        
        portfolio_df = db.get_portfolio_summary()
        if portfolio_df.empty:
            print("❌ 无持仓数据")
            return self.alerts
            
        portfolio_df['Quantity'] = pd.to_numeric(portfolio_df['Quantity'], errors='coerce').fillna(0)
        portfolio_df = portfolio_df[portfolio_df['Quantity'] > 0.01]
        portfolio_df = ut.update_portfolio_valuation(portfolio_df)
        
        cash = db.get_cash_balance()
        invested = db.get_total_invested()
        market_val = portfolio_df['Market Value'].sum()
        net_asset = market_val + cash
        
        # 运行所有检查
        self.check_concentration(portfolio_df)
        self.check_cash(cash, net_asset)
        self.check_leverage(market_val, net_asset)
        self.check_sector_concentration(portfolio_df)
        self.check_loss_ratio(portfolio_df)
        self.check_max_drawdown_risk(portfolio_df)
        
        return self.alerts
        
    def print_alerts(self):
        """打印告警"""
        if not self.alerts:
            print("✅ 无告警")
            return
            
        # 按等级排序
        level_order = {"CRITICAL": 0, "WARNING": 1, "INFO": 2}
        self.alerts.sort(key=lambda x: level_order.get(x.level, 99))
        
        print("=" * 50)
        print("🚨 IM 风险告警报告")
        print("=" * 50)
        print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"告警数量: {len(self.alerts)}\n")
        
        for alert in self.alerts:
            print(str(alert))
            if alert.action:
                print(f"   💡 建议: {alert.action}")
            print("")
            
        print("=" * 50)
        
    def generate_report(self):
        """生成告警报告（Markdown 格式）"""
        if not self.alerts:
            return None
            
        level_order = {"CRITICAL": 0, "WARNING": 1, "INFO": 2}
        self.alerts.sort(key=lambda x: level_order.get(x.level, 99))
        
        report = f"""# 🚨 IM 风险告警报告

**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**告警数量**: {len(self.alerts)}

---

"""
        
        for alert in self.alerts:
            emoji = {
                "INFO": "ℹ️",
                "WARNING": "⚠️",
                "CRITICAL": "🚨"
            }.get(alert.level, "❓")
            
            report += f"### {emoji} **[{alert.level}]** {alert.title}\n\n"
            report += f"{alert.message}\n\n"
            if alert.action:
                report += f"💡 **建议**: {alert.action}\n\n"
            report += "---\n\n"
            
        return report
        
    def save_report(self, filepath=None):
        """保存告警报告"""
        report = self.generate_report()
        if report is None:
            print("✅ 无告警，无需保存")
            return
            
        if filepath is None:
            alerts_dir = Path(__file__).parent / 'alerts'
            alerts_dir.mkdir(exist_ok=True)
            filepath = alerts_dir / f"{datetime.now().strftime('%Y-%m-%d')}-alerts.md"
            
        filepath.write_text(report)
        print(f"✅ 告警报告已保存: {filepath}")


def main():
    system = AlertSystem()
    alerts = system.run_all_checks()
    system.print_alerts()
    system.save_report()


if __name__ == "__main__":
    main()
