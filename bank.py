import time
import math
from astrbot.api import logger
from .database import Database
from .config import Config

BOUNDARY_1 = 50000   # ≤5w
BOUNDARY_2 = 100000  # 5w~10w

class BankModule:
    def __init__(self, db: Database, config: Config):
        self.db = db
        self.config = config

    def _get_rate_tag(self, total_deposit_before):
        """根据存入时的总存款确定利率标签"""
        if total_deposit_before <= BOUNDARY_1:
            return "low"
        elif total_deposit_before <= BOUNDARY_2:
            return "mid"
        else:
            return "high"

    def _get_rate(self, rate_tag):
        if rate_tag == "low":
            return self.config.bank_rate_low
        elif rate_tag == "mid":
            return self.config.bank_rate_mid
        else:
            return self.config.bank_rate_high

    def get_interest_rates_display(self):
        """获取利率展示"""
        return (
            f"🏦 银行存款利率：\n"
            f"存款 ≤ 5w：日利率 {self.config.bank_rate_low*100:.1f}%\n"
            f"5w < 存款 ≤ 10w：日利率 {self.config.bank_rate_mid*100:.1f}%\n"
            f"存款 > 10w：日利率 {self.config.bank_rate_high*100:.1f}%\n"
            f"利息按日自动结算，提前取出无收益"
        )

    def deposit(self, user_id, amount):
        """存款"""
        if amount <= 0:
            return "❌ 存款金额必须大于0"
        balance = self.db.get_balance(user_id)
        if balance < amount:
            return f"❌ 余额不足！当前余额：{balance}，需要：{amount}"
        # 扣货币
        self.db.add_balance(user_id, -amount)
        # 获取存入时的总存款
        total_before = self.db.get_total_deposit(user_id)
        rate_tag = self._get_rate_tag(total_before)
        self.db.add_deposit(user_id, amount, rate_tag)
        rate = self._get_rate(rate_tag)
        return f"✅ 存款成功！存入 {amount} {self.config.currency_name}\n利率：{rate*100:.1f}%（按存入时总存款 {total_before} 确定）"

    def check_withdraw(self, user_id, index=0):
        """检查取款，返回 (该笔存款信息, 提示)"""
        deposits = self.db.get_deposits(user_id)
        if not deposits:
            return None, "❌ 你没有存款"
        if index < 0 or index >= len(deposits):
            return None, "❌ 存款索引无效"
        dep = deposits[index]
        if not dep.get("active", True):
            return None, "❌ 该笔存款已取出"
        rate = self._get_rate(dep["rate_tag"])
        elapsed_days = (time.time() - dep["deposit_time"]) / 86400
        if elapsed_days < 1:
            # 未满24小时提前取出，无收益
            return dep, f"⚠️ 提前取出无收益，仅返还本金 {dep['amount']} {self.config.currency_name}，确认？(回复 确认取出)"
        days = int(elapsed_days)
        interest = int(dep["amount"] * rate * days / 365)
        total = dep["amount"] + interest
        return dep, f"⚠️ 取出该笔存款？本金 {dep['amount']}，利息 {interest}，合计 {total} {self.config.currency_name}(回复 确认取出)"

    def confirm_withdraw(self, user_id, index=0):
        """确认取款"""
        deposits = self.db.get_deposits(user_id)
        if not deposits or index < 0 or index >= len(deposits):
            return "❌ 存款不存在"
        dep = deposits[index]
        if not dep.get("active", True):
            return "❌ 该笔存款已取出"
        rate = self._get_rate(dep["rate_tag"])
        elapsed_days = (time.time() - dep["deposit_time"]) / 86400
        if elapsed_days < 1:
            # 无利息
            self.db.add_balance(user_id, dep["amount"])
            self.db.remove_deposit(user_id, index)
            return f"✅ 提前取出成功！返还本金 {dep['amount']} {self.config.currency_name}（无利息）"
        days = int(elapsed_days)
        interest = int(dep["amount"] * rate * days / 365)
        total = dep["amount"] + interest
        self.db.add_balance(user_id, total)
        self.db.remove_deposit(user_id, index)
        return f"✅ 取出成功！本金 {dep['amount']} + 利息 {interest} = {total} {self.config.currency_name}"

    def check_interest(self, user_id):
        """检查并发放利息（每日自动）"""
        deposits = self.db.get_deposits(user_id)
        now = time.time()
        total_interest = 0
        updated_deposits = []
        for dep in deposits:
            if not dep.get("active", True):
                updated_deposits.append(dep)
                continue
            rate = self._get_rate(dep["rate_tag"])
            elapsed = now - dep["last_interest_time"]
            if elapsed >= 86400:  # 满24小时
                days = int(elapsed / 86400)
                interest = int(dep["amount"] * rate * days / 365)
                if interest > 0:
                    self.db.add_balance(user_id, interest)
                    total_interest += interest
                dep["last_interest_time"] += days * 86400
            updated_deposits.append(dep)
        self.db.save_deposits(user_id, updated_deposits)
        return total_interest

    def get_deposit_info(self, user_id):
        """获取存款详情"""
        deposits = self.db.get_deposits(user_id)
        if not deposits:
            return "📭 你没有任何存款"
        total = 0
        lines = []
        for i, dep in enumerate(deposits):
            if not dep.get("active", True):
                continue
            rate = self._get_rate(dep["rate_tag"])
            amount = dep["amount"]
            total += amount
            elapsed = time.time() - dep["deposit_time"]
            days = int(elapsed / 86400)
            interest = int(amount * rate * days / 365)
            lines.append(f"{i+1}. {amount} {self.config.currency_name} | 利率 {rate*100:.1f}% | 存了 {days} 天 | 利息 {interest}")
        if not lines:
            return "📭 你没有任何存款"
        lines.insert(0, f"📊 你的存款（共 {total} {self.config.currency_name}）：")
        return "\n".join(lines)