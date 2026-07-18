import random
import time
from astrbot.api import logger
from .database import Database
from .config import Config

class FateModule:
    def __init__(self, db: Database, config: Config):
        self.db = db
        self.config = config

    def _roll_fate(self) -> tuple:
        """返回 (is_good, multiplier)"""
        r = random.random()
        if r <= self.config.fate_good_prob:
            return True, 2.0
        else:
            # 失败时使用配置的惩罚倍率，默认0.0即扣100%
            return False, self.config.fate_loss_multiplier

    def _get_random_text(self, texts_list, **kwargs):
        """从列表中随机选取一条文本并格式化"""
        if not texts_list:
            return "命运结果"
        text = random.choice(texts_list)
        try:
            return text.format(**kwargs)
        except Exception as e:
            logger.error(f"格式化命运文本失败: {e}")
            return text

    def _check_easter_egg(self, user_id: str, amount: int):
        """彩蛋检查"""
        if amount in self.config.fate_easter_eggs:
            if amount == 712721:
                gain = 712721
                new_balance = self.db.add_balance(user_id, gain)
                return f"✨ 彩蛋！你触发了幸运数字 {amount}，获得 {gain} {self.config.currency_name}！当前余额：{new_balance}\n关注天依谢谢喵^_^"
        return None

    async def process_fate(self, user_id: str, user_name: str, amount: int) -> str:
        if amount <= 0:
            return f"⚠️ 请输入大于0的{self.config.currency_name}数量，例如：命运 100"

        # 冷却检查
        last_time = self.db.get_fate_cooldown(user_id)
        now = time.time()
        if last_time > 0:
            elapsed = now - last_time
            if elapsed < self.config.fate_cooldown_seconds:
                remaining = int(self.config.fate_cooldown_seconds - elapsed)
                return f"⏳ 命运冷却中，还剩 {remaining} 秒，请稍后再试～"

        current_balance = self.db.get_balance(user_id)
        if current_balance < amount:
            return f"❌ 你的{self.config.currency_name}不足！当前余额：{current_balance}，需要：{amount}"

        easter_text = self._check_easter_egg(user_id, amount)
        if easter_text:
            return easter_text

        is_good, multiplier = self._roll_fate()
        if is_good:
            gain = int(amount * (multiplier - 1))
            new_balance = current_balance + gain
            self.db.set_balance(user_id, new_balance)
            text = self._get_random_text(
                self.config.fate_good_texts,
                gain=gain,
                balance=new_balance,
                amount=amount,
                currency=self.config.currency_name
            )
            logger.info(f"命运：用户 {user_name}({user_id}) 命运 {amount}，成功，获得 {gain}，余额 {current_balance} -> {new_balance}")
        else:
            # multiplier=0.0 时 loss = 押注金额的100%
            loss = int(amount * (1 - multiplier))
            new_balance = current_balance - loss
            self.db.set_balance(user_id, new_balance)
            text = self._get_random_text(
                self.config.fate_bad_texts,
                loss=loss,
                balance=new_balance,
                amount=amount,
                currency=self.config.currency_name
            )
            logger.info(f"命运：用户 {user_name}({user_id}) 命运 {amount}，失败，损失 {loss}，余额 {current_balance} -> {new_balance}")

        # 更新冷却时间
        self.db.set_fate_cooldown(user_id, now)

        return text