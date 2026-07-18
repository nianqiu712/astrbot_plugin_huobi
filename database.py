import json
import os
from datetime import datetime, timedelta
from astrbot.api import logger

class Database:
    def __init__(self, data_dir):
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)
        self.balance_file = os.path.join(self.data_dir, "balance.json")
        self.sign_file = os.path.join(self.data_dir, "sign_records.json")
        self.fate_cooldown_file = os.path.join(self.data_dir, "fate_cooldown.json")
        
        self._init_file(self.balance_file, {})
        self._init_file(self.sign_file, {})
        self._init_file(self.fate_cooldown_file, {})

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

    def get_balance(self, user_id):
        balance_data = self._read_file(self.balance_file)
        return balance_data.get(str(user_id), 0)

    def add_balance(self, user_id, amount):
        balance_data = self._read_file(self.balance_file)
        user_id_str = str(user_id)
        balance_data[user_id_str] = balance_data.get(user_id_str, 0) + amount
        self._write_file(self.balance_file, balance_data)
        return balance_data[user_id_str]

    def set_balance(self, user_id, amount):
        balance_data = self._read_file(self.balance_file)
        balance_data[str(user_id)] = amount
        self._write_file(self.balance_file, balance_data)
        return amount

    def get_sign_record(self, user_id):
        sign_data = self._read_file(self.sign_file)
        return sign_data.get(str(user_id), {})

    def set_sign_record(self, user_id, flower_value):
        """flower_value: 存储当天的日期字符串，用于判断是否已签到"""
        sign_data = self._read_file(self.sign_file)
        user_id_str = str(user_id)
        sign_data[user_id_str] = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "flower": flower_value
        }
        self._clean_old_sign_records(sign_data)
        self._write_file(self.sign_file, sign_data)

    def _clean_old_sign_records(self, sign_data):
        seven_days_ago = datetime.now() - timedelta(days=7)
        to_delete = []
        for user_id, record in sign_data.items():
            try:
                record_time = datetime.strptime(record["time"], "%Y-%m-%d %H:%M:%S")
                if record_time < seven_days_ago:
                    to_delete.append(user_id)
            except:
                to_delete.append(user_id)
        for user_id in to_delete:
            del sign_data[user_id]

    def get_fate_cooldown(self, user_id):
        cooldown_data = self._read_file(self.fate_cooldown_file)
        return cooldown_data.get(str(user_id), 0)

    def set_fate_cooldown(self, user_id, timestamp):
        cooldown_data = self._read_file(self.fate_cooldown_file)
        cooldown_data[str(user_id)] = timestamp
        self._write_file(self.fate_cooldown_file, cooldown_data)