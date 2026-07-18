import json
from astrbot.api import logger

class Config:
    def __init__(self, config_obj):
        self.raw_config = config_obj
        self.admin_qq = str(config_obj.get('admin_qq', ""))
        self.currency_name = config_obj.get('currency_name', "金币")
        self.sign_reward_min = config_obj.get('sign_reward_min', 50)
        self.sign_reward_max = config_obj.get('sign_reward_max', 150)
        self.sign_text = config_obj.get('sign_text')
        if self.sign_text:
            self.sign_text = self.sign_text.replace('\\n', '\n')
        
        self.flower_value_config = self._parse_json(
            config_obj.get('flower_value_config'),
            [{"min": 0, "max": 20, "text": "桃花败残，凌乱枝桠"},
             {"min": 21, "max": 40, "text": "桃花含苞，静待花开"},
             {"min": 41, "max": 60, "text": "桃花微绽，若见呢喃"},
             {"min": 61, "max": 80, "text": "桃花满盛，落英纷然"},
             {"min": 81, "max": 100, "text": "桃之夭夭，灼灼其华！"}]
        )
        self.fate_good_prob = config_obj.get('fate_good_prob', 0.55)
        self.fate_good_texts = self._parse_json(config_obj.get('fate_good_texts'),
            ["🎉 鸿运当头！你获得了 {gain} {currency}！\n当前余额：{balance}"])
        if self.fate_good_texts:
            self.fate_good_texts = [t.replace('\\n', '\n') for t in self.fate_good_texts]
        self.fate_bad_texts = self._parse_json(config_obj.get('fate_bad_texts'),
            ["😭 时运不济！你损失了 {loss} {currency}！\n当前余额：{balance}"])
        if self.fate_bad_texts:
            self.fate_bad_texts = [t.replace('\\n', '\n') for t in self.fate_bad_texts]
        self.fate_cooldown_seconds = config_obj.get('fate_cooldown_seconds', 120)
        self.fate_easter_eggs = self._parse_json(config_obj.get('fate_easter_eggs'), [712721])
        self.fate_loss_multiplier = config_obj.get('fate_loss_multiplier', 0.0)

        self.gacha_enabled = config_obj.get('gacha_enabled', True)
        self.gacha_cost = int(config_obj.get('gacha_cost', 200))
        self.gacha_initial_currency = int(config_obj.get('gacha_initial_currency', 2000))
        self.gacha_initial_tickets = int(config_obj.get('gacha_initial_tickets', 20))

        self.bank_enabled = config_obj.get('bank_enabled', True)
        self.bank_rate_low = config_obj.get('bank_daily_interest_rate_3', 0.10)
        self.bank_rate_mid = config_obj.get('bank_daily_interest_rate_2', 0.05)
        self.bank_rate_high = config_obj.get('bank_daily_interest_rate_1', 0.02)

        self.set_bonus_interest = config_obj.get('set_bonus_interest', 0.05)

        logger.info(f"✅ 配置加载完成，管理员: {self.admin_qq}")

    def _parse_json(self, value, default):
        if value is None:
            return default
        if isinstance(value, str):
            try:
                return json.loads(value)
            except:
                return default
        return value

    def is_admin(self, user_id: str) -> bool:
        return str(user_id) == self.admin_qq

    def get_flower_text(self, value: int) -> str:
        for cfg in self.flower_value_config:
            if cfg["min"] <= value <= cfg["max"]:
                return cfg["text"]
        return "桃花值范围异常"