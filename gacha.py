import random
import time
import json
from astrbot.api import logger
from .database import Database, SOLAR_TERMS

POOL_3 = {
    "name": "三等奖池",
    "prob": 0.40,
    "weights": [0.45, 0.25, 0.2895, 0.01, 0.0005],
    "rewards": [16, 64, 256, 1024, 5000],
    "jackpot_fixed": 5000,
    "target_expect": 110
}

POOL_2 = {
    "name": "二等奖池",
    "prob": 0.30,
    "weights": [0.45, 0.25, 0.2895, 0.01, 0.0005],
    "rewards": [22, 88, 352, 1408, 10000],
    "jackpot_fixed": 10000,
    "target_expect": 150
}

POOL_1 = {
    "name": "一等奖池",
    "prob": 0.05,
    "weights": [0.45, 0.25, 0.2895, 0.01, 0.0005],
    "rewards": [51, 204, 816, 3264, 30000],
    "jackpot_fixed": 30000,
    "target_expect": 360
}

POOLS = [POOL_3, POOL_2, POOL_1]

class GachaModule:
    def __init__(self, db: Database, config):
        self.db = db
        self.config = config

    def _get_pool_reward(self, pool):
        r = random.random()
        cumulative = 0
        for i, w in enumerate(pool["weights"]):
            cumulative += w
            if r < cumulative:
                if i == 4:
                    return pool["jackpot_fixed"], True
                return pool["rewards"][i], False
        return pool["rewards"][0], False

    def _select_pool(self):
        r = random.random()
        cumulative = 0
        for pool in POOLS:
            cumulative += pool["prob"]
            if r < cumulative:
                return pool
        return POOLS[0]

    def _get_missing_cards(self, user_id):
        cards = self.db.get_cards(user_id)
        return [t for t in SOLAR_TERMS if cards.get(t, 0) == 0]

    def _get_card_threshold(self, user_id):
        collected = 24 - len(self._get_missing_cards(user_id))
        return collected >= 17

    def _draw_card(self, user_id):
        """抽卡牌，返回(卡牌名称, 保底提示)"""
        missing = self._get_missing_cards(user_id)
        pity = self.db.get_gacha_pity(user_id)
        hint = ""

        # 积累7次及以上给出保底提示
        if pity["accumulated"] >= 7 and missing:
            remaining = 10 - pity["accumulated"]
            hint = f"⏳ 已积累{pity['accumulated']}次重复，剩余{remaining}次保底必出新卡！"

        # 强制出新卡
        if pity["forced_new"] and missing:
            self.db.set_gacha_pity(user_id, forced_new=False, counter=0, accumulated=0)
            card = random.choice(missing)
            return card, hint

        if missing and self._get_card_threshold(user_id):
            all_cards = self.db.get_cards(user_id)
            total = sum(all_cards.values())
            if total > 0:
                weighted = []
                for term in SOLAR_TERMS:
                    if term in missing:
                        weighted.extend([term] * 1)
                    else:
                        weighted.extend([term] * (all_cards[term] + 1))
                card = random.choice(weighted)
            else:
                card = random.choice(SOLAR_TERMS)
        else:
            card = random.choice(SOLAR_TERMS)

        cards = self.db.get_cards(user_id)
        if cards.get(card, 0) > 0:
            counter = pity["counter"] + 1
            accumulated = pity["accumulated"] + 1
            forced_new = counter >= 10
            if forced_new:
                self.db.set_gacha_pity(user_id, counter=0, forced_new=True, accumulated=accumulated)
            else:
                self.db.set_gacha_pity(user_id, counter=counter, accumulated=accumulated)
        else:
            self.db.set_gacha_pity(user_id, counter=0, forced_new=False, accumulated=0)

        return card, hint

    def single_gacha(self, user_id, user_name=""):
        """单抽，返回结果列表"""
        results = []
        if not self.config.gacha_enabled:
            return ["❌ 抽卡系统已关闭"]

        tickets = self.db.get_tickets(user_id)
        cost = self.config.gacha_cost
        balance = self.db.get_balance(user_id)

        if tickets < 1:
            if balance >= cost:
                self.db.add_balance(user_id, -cost)
                self.db.add_tickets(user_id, 1)
                tickets = 1
            else:
                return [f"❌ 抽卡次数不足，且{self.config.currency_name}不够（需要{cost}，当前{balance}）"]

        self.db.add_tickets(user_id, -1)

        r = random.random()
        if r < 0.25:
            card, hint = self._draw_card(user_id)
            self.db.add_card(user_id, card, 1)
            results.append(card)
            if hint:
                results.append(hint)
            if self.db.check_complete_set(user_id):
                results.append(f"🌟 集齐二十四节气！套数+1，收益增加{(self.config.set_bonus_interest*100):.0f}%")
        else:
            pool = self._select_pool()
            reward, is_jackpot = self._get_pool_reward(pool)
            self.db.add_balance(user_id, reward)
            if is_jackpot:
                results.append(f"🎉🎉🎉 超级大奖！获得 {reward} {self.config.currency_name}")
            else:
                results.append(f"获得 {reward}{self.config.currency_name}")

        return results

    def multi_gacha(self, user_id, count=10, user_name=""):
        """十连抽"""
        all_results = []
        if not self.config.gacha_enabled:
            return ["❌ 抽卡系统已关闭"]

        cost = self.config.gacha_cost
        balance = self.db.get_balance(user_id)
        tickets = self.db.get_tickets(user_id)

        needed_tickets = count
        missing_tickets = max(0, needed_tickets - tickets)
        needed_currency = missing_tickets * cost

        if missing_tickets > 0:
            if balance < needed_currency:
                return [f"❌ 货币不足！缺少{missing_tickets}抽，需要额外{needed_currency}{self.config.currency_name}，当前余额{balance}"]
            self.db.add_balance(user_id, -needed_currency)
            self.db.add_tickets(user_id, missing_tickets)

        self.db.add_tickets(user_id, -count)

        for i in range(count):
            r = random.random()
            if r < 0.25:
                card, hint = self._draw_card(user_id)
                self.db.add_card(user_id, card, 1)
                all_results.append(card)
                if hint:
                    all_results.append(hint)
                if self.db.check_complete_set(user_id):
                    all_results.append(f"🌟 集齐二十四节气！套数+1")
            else:
                pool = self._select_pool()
                reward, is_jackpot = self._get_pool_reward(pool)
                self.db.add_balance(user_id, reward)
                if is_jackpot:
                    all_results.append(f"🎉🎉🎉 超级大奖！获得 {reward} {self.config.currency_name}")
                else:
                    all_results.append(f"获得 {reward}{self.config.currency_name}")

        return all_results