import random
import time
from astrbot.api import logger
from .database import Database
from .config import Config

class SignModule:
    def __init__(self, db: Database, config: Config):
        self.db = db
        self.config = config

    def has_signed_today(self, user_id: str) -> bool:
        """检查用户今天是否已签到"""
        record = self.db.get_sign_record(user_id)
        if not record:
            return False
        today = time.strftime("%Y%m%d")
        # record 结构: {"time": "...", "flower": date_str}
        return record.get("flower") == today

    def mark_signed_today(self, user_id: str):
        """标记用户今天已签到，用日期作为flower值存储"""
        today = time.strftime("%Y%m%d")
        self.db.set_sign_record(user_id, today)

    def _random_reward(self) -> int:
        return random.randint(self.config.sign_reward_min, self.config.sign_reward_max)

    def _random_flower_value(self) -> int:
        return random.randint(0, 100)

    async def process_sign(self, event) -> str:
        user_id = event.get_sender_id()
        user_name = event.get_sender_name() or str(user_id)

        if self.has_signed_today(user_id):
            return "⏰ 你今天已经签到过了，明天再来吧～"

        reward = self._random_reward()
        flower_value = self._random_flower_value()
        flower_text = self.config.get_flower_text(flower_value)

        new_balance = self.db.add_balance(user_id, reward)

        self.mark_signed_today(user_id)

        text = self.config.sign_text or "🎉 {user} 签到成功，获得 {reward} {currency}\n桃花值：{flower_value} {flower_text}\n当前余额：{balance}"
        result = text.format(
            user=user_name,
            reward=reward,
            currency=self.config.currency_name,
            flower_value=flower_value,
            flower_text=flower_text,
            balance=new_balance
        )

        logger.info(f"用户 {user_name}({user_id}) 签到成功，获得 {reward}\n桃花值 {flower_value}")
        return result