import json
import os
import time
from datetime import datetime, timedelta
from astrbot.api import logger

SOLAR_TERMS = ["立春", "雨水", "惊蛰", "春分", "清明", "谷雨",
               "立夏", "小满", "芒种", "夏至", "小暑", "大暑",
               "立秋", "处暑", "白露", "秋分", "寒露", "霜降",
               "立冬", "小雪", "大雪", "冬至", "小寒", "大寒"]

SOLAR_TERMS_SPRING = ["立春", "雨水", "惊蛰", "春分", "清明", "谷雨"]
SOLAR_TERMS_SUMMER = ["立夏", "小满", "芒种", "夏至", "小暑", "大暑"]
SOLAR_TERMS_AUTUMN = ["立秋", "处暑", "白露", "秋分", "寒露", "霜降"]
SOLAR_TERMS_WINTER = ["立冬", "小雪", "大雪", "冬至", "小寒", "大寒"]

class Database:
    def __init__(self, data_dir):
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)
        self.balance_file = os.path.join(self.data_dir, "balance.json")
        self.sign_file = os.path.join(self.data_dir, "sign_records.json")
        self.fate_cooldown_file = os.path.join(self.data_dir, "fate_cooldown.json")
        self.user_data_file = os.path.join(self.data_dir, "user_data.json")
        self.deposit_file = os.path.join(self.data_dir, "deposits.json")

        self._init_file(self.balance_file, {})
        self._init_file(self.sign_file, {})
        self._init_file(self.fate_cooldown_file, {})
        self._init_file(self.user_data_file, {})
        self._init_file(self.deposit_file, {})

    def _init_file(self, file_path, default):
        if not os.path.exists(file_path):
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(default, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.error(f"初始化文件 {file_path} 失败: {e}")

    def _read_file(self, file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"读取文件 {file_path} 失败: {e}")
            return {}

    def _write_file(self, file_path, data):
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"写入文件 {file_path} 失败: {e}")

    # ========== 余额 ==========
    def get_balance(self, user_id):
        balance_data = self._read_file(self.balance_file)
        return balance_data.get(str(user_id), 0)

    def add_balance(self, user_id, amount):
        balance_data = self._read_file(self.balance_file)
        uid = str(user_id)
        balance_data[uid] = balance_data.get(uid, 0) + amount
        self._write_file(self.balance_file, balance_data)
        return balance_data[uid]

    def set_balance(self, user_id, amount):
        balance_data = self._read_file(self.balance_file)
        balance_data[str(user_id)] = amount
        self._write_file(self.balance_file, balance_data)
        return amount

    # ========== 签到 ==========
    def get_sign_record(self, user_id):
        sign_data = self._read_file(self.sign_file)
        return sign_data.get(str(user_id), {})

    def set_sign_record(self, user_id, flower_value):
        sign_data = self._read_file(self.sign_file)
        uid = str(user_id)
        sign_data[uid] = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "flower": flower_value
        }
        self._clean_old_sign_records(sign_data)
        self._write_file(self.sign_file, sign_data)

    def _clean_old_sign_records(self, sign_data):
        seven_days_ago = datetime.now() - timedelta(days=7)
        for uid, record in list(sign_data.items()):
            try:
                record_time = datetime.strptime(record["time"], "%Y-%m-%d %H:%M:%S")
                if record_time < seven_days_ago:
                    del sign_data[uid]
            except:
                del sign_data[uid]

    # ========== 命运冷却 ==========
    def get_fate_cooldown(self, user_id):
        cooldown_data = self._read_file(self.fate_cooldown_file)
        return cooldown_data.get(str(user_id), 0)

    def set_fate_cooldown(self, user_id, timestamp):
        cooldown_data = self._read_file(self.fate_cooldown_file)
        cooldown_data[str(user_id)] = timestamp
        self._write_file(self.fate_cooldown_file, cooldown_data)

    # ========== 用户数据(抽卡次数、卡牌、集齐套数) ==========
    def _init_user(self, user_id, initial_currency=2000, initial_tickets=20):
        """如果用户不存在则初始化"""
        user_data = self._read_file(self.user_data_file)
        uid = str(user_id)
        if uid not in user_data:
            user_data[uid] = {
                "tickets": initial_tickets,
                "cards": {term: 0 for term in SOLAR_TERMS},
                "sets_completed": 0,
                "gacha_pity_counter": 0,     # 连续重复次数
                "gacha_forced_new": False,    # 下次是否必出新卡
                "gacha_accumulated": 0        # 积累的保底次数
            }
            self._write_file(self.user_data_file, user_data)
            # 同时初始化余额
            bal = self._read_file(self.balance_file)
            if uid not in bal:
                bal[uid] = initial_currency
                self._write_file(self.balance_file, bal)
        return user_data[uid]

    def get_user_data(self, user_id, initial_currency=2000, initial_tickets=20):
        self._init_user(user_id, initial_currency, initial_tickets)
        user_data = self._read_file(self.user_data_file)
        return user_data.get(str(user_id), {})

    def save_user_data(self, user_id, data):
        user_data = self._read_file(self.user_data_file)
        user_data[str(user_id)] = data
        self._write_file(self.user_data_file, user_data)

    def get_tickets(self, user_id):
        data = self.get_user_data(user_id)
        return data.get("tickets", 0)

    def set_tickets(self, user_id, tickets):
        data = self.get_user_data(user_id)
        data["tickets"] = max(0, tickets)
        self.save_user_data(user_id, data)

    def add_tickets(self, user_id, amount):
        data = self.get_user_data(user_id)
        data["tickets"] = data.get("tickets", 0) + amount
        self.save_user_data(user_id, data)
        return data["tickets"]

    def get_cards(self, user_id):
        data = self.get_user_data(user_id)
        return data.get("cards", {term: 0 for term in SOLAR_TERMS})

    def add_card(self, user_id, card_name, count=1):
        data = self.get_user_data(user_id)
        if "cards" not in data:
            data["cards"] = {term: 0 for term in SOLAR_TERMS}
        data["cards"][card_name] = data["cards"].get(card_name, 0) + count
        self.save_user_data(user_id, data)
        return data["cards"][card_name]

    def set_cards(self, user_id, card_name, count):
        data = self.get_user_data(user_id)
        if "cards" not in data:
            data["cards"] = {term: 0 for term in SOLAR_TERMS}
        data["cards"][card_name] = max(0, count)
        self.save_user_data(user_id, data)

    def get_sets_completed(self, user_id):
        data = self.get_user_data(user_id)
        return data.get("sets_completed", 0)

    def set_sets_completed(self, user_id, count):
        data = self.get_user_data(user_id)
        data["sets_completed"] = count
        self.save_user_data(user_id, data)

    def get_gacha_pity(self, user_id):
        data = self.get_user_data(user_id)
        return {
            "counter": data.get("gacha_pity_counter", 0),
            "forced_new": data.get("gacha_forced_new", False),
            "accumulated": data.get("gacha_accumulated", 0)
        }

    def set_gacha_pity(self, user_id, counter=None, forced_new=None, accumulated=None):
        data = self.get_user_data(user_id)
        if counter is not None:
            data["gacha_pity_counter"] = counter
        if forced_new is not None:
            data["gacha_forced_new"] = forced_new
        if accumulated is not None:
            data["gacha_accumulated"] = accumulated
        self.save_user_data(user_id, data)

    def check_complete_set(self, user_id):
        """检查是否集齐一套，集齐则消耗一套并返回True"""
        cards = self.get_cards(user_id)
        if all(count >= 1 for count in cards.values()):
            for term in SOLAR_TERMS:
                cards[term] -= 1
            data = self.get_user_data(user_id)
            data["cards"] = cards
            data["sets_completed"] = data.get("sets_completed", 0) + 1
            self.save_user_data(user_id, data)
            return True
        return False

    # ========== 银行存款 ==========
    def get_deposits(self, user_id):
        deposits = self._read_file(self.deposit_file)
        return deposits.get(str(user_id), [])

    def add_deposit(self, user_id, amount, rate_tag):
        """rate_tag: 'low' (≤5w), 'mid' (5w~10w), 'high' (>10w)"""
        deposits = self._read_file(self.deposit_file)
        uid = str(user_id)
        if uid not in deposits:
            deposits[uid] = []
        deposits[uid].append({
            "amount": amount,
            "rate_tag": rate_tag,
            "deposit_time": time.time(),
            "last_interest_time": time.time(),
            "active": True
        })
        self._write_file(self.deposit_file, deposits)

    def remove_deposit(self, user_id, index):
        deposits = self._read_file(self.deposit_file)
        uid = str(user_id)
        if uid in deposits and 0 <= index < len(deposits[uid]):
            deposit = deposits[uid].pop(index)
            self._write_file(self.deposit_file, deposits)
            return deposit
        return None

    def update_deposit_interest_time(self, user_id, index, new_time):
        deposits = self._read_file(self.deposit_file)
        uid = str(user_id)
        if uid in deposits and 0 <= index < len(deposits[uid]):
            deposits[uid][index]["last_interest_time"] = new_time
            self._write_file(self.deposit_file, deposits)

    def save_deposits(self, user_id, deposit_list):
        deposits = self._read_file(self.deposit_file)
        deposits[str(user_id)] = deposit_list
        self._write_file(self.deposit_file, deposits)

    def get_total_deposit(self, user_id):
        total = 0
        for dep in self.get_deposits(user_id):
            if dep.get("active", True):
                total += dep["amount"]
        return total