from pathlib import Path
import re
import time
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api import AstrBotConfig
from astrbot.api.message_components import At

from .database import Database, SOLAR_TERMS, SOLAR_TERMS_SPRING, SOLAR_TERMS_SUMMER, SOLAR_TERMS_AUTUMN, SOLAR_TERMS_WINTER
from .config import Config
from .sign import SignModule
from .fate import FateModule
from .gacha import GachaModule
from .bank import BankModule

PENDING_WITHDRAW = {}  # {user_id: {"index": int, "time": float}}

@register(
    name="sign_system",
    author="YourName",
    desc="签到+命运+抽卡+银行 多功能货币系统 v2.0",
    version="2.0.0"
)
class SignSystemPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        logger.info("🚀 开始初始化签到系统 v2...")

        try:
            # 数据存放在插件目录上级的 sign_system_data 中，git更新不会覆盖
            plugin_dir = Path(__file__).parent
            self.data_dir = plugin_dir.parent / "sign_system_data"
            self.data_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"✅ 数据目录: {self.data_dir}")
        except Exception as e:
            logger.error(f"❌ 创建数据目录失败: {e}")
            self.data_dir = Path(".") / "sign_system_data"
            self.data_dir.mkdir(parents=True, exist_ok=True)

        try:
            self.db = Database(str(self.data_dir))
            logger.info("✅ Database 初始化成功")
        except Exception as e:
            logger.error(f"❌ Database 初始化失败: {e}")
            self.db = None

        try:
            self.config = Config(config)
            logger.info(f"✅ Config 初始化成功")
        except Exception as e:
            logger.error(f"❌ Config 初始化失败: {e}")
            self.config = None

        if self.db and self.config:
            self.sign = SignModule(self.db, self.config)
            self.fate = FateModule(self.db, self.config)
            self.gacha = GachaModule(self.db, self.config)
            self.bank = BankModule(self.db, self.config)
            logger.info("✅ 所有模块初始化成功")
        else:
            self.sign = self.fate = self.gacha = self.bank = None

        logger.info("🎉 签到系统 v2 初始化完成")

    # ========== 签到 ==========
    @filter.regex(r"^(签到|打卡|每日签到)$")
    async def sign_in(self, event: AstrMessageEvent):
        if not self.sign:
            yield event.plain_result("❌ 签到模块未初始化")
            return
        try:
            result = await self.sign.process_sign(event)
            yield event.plain_result(result)
        except Exception as e:
            logger.error(f"签到报错: {e}")
            yield event.plain_result("❌ 签到失败")

    # ========== 余额 ==========
    @filter.command("余额")
    async def my_money(self, event: AstrMessageEvent):
        if not self.db or not self.config:
            yield event.plain_result("❌ 插件未初始化")
            return
        try:
            user_id = event.get_sender_id()
            balance = self.db.get_balance(user_id)
            tickets = self.db.get_tickets(user_id)
            sets = self.db.get_sets_completed(user_id)
            currency = self.config.currency_name
            yield event.plain_result(
                f"💰 你的{currency}余额：{balance}\n"
                f"🎫 抽卡次数：{tickets}\n"
                f"🀄 已集齐二十四节气：{sets} 套"
            )
        except Exception as e:
            logger.error(f"余额报错: {e}")
            yield event.plain_result("❌ 查询失败")

    # ========== 命运 ==========
    @filter.regex(r"^命运\s*(\d+)$")
    async def fate_game(self, event: AstrMessageEvent):
        if not self.fate:
            yield event.plain_result("❌ 命运模块未初始化")
            return
        try:
            m = re.search(r"命运\s*(\d+)", event.message_str.strip())
            if not m:
                yield event.plain_result("❌ 格式错误，例如：命运 100")
                return
            bet = int(m.group(1))
            uid = event.get_sender_id()
            uname = event.get_sender_name() or str(uid)
            result = await self.fate.process_fate(uid, uname, bet)
            yield event.plain_result(result)
        except Exception as e:
            logger.error(f"命运报错: {e}")
            yield event.plain_result("❌ 命运失败")

    # ========== 单抽 ==========
    @filter.regex(r"^单抽$")
    async def single_gacha(self, event: AstrMessageEvent):
        if not self.gacha:
            yield event.plain_result("❌ 抽卡模块未初始化")
            return
        try:
            uid = event.get_sender_id()
            uname = event.get_sender_name() or str(uid)
            results = self.gacha.single_gacha(uid, uname)
            lines = "\n".join(results)
            yield event.plain_result(f"@{uname}\n{lines}")
        except Exception as e:
            logger.error(f"单抽报错: {e}")
            yield event.plain_result("❌ 抽卡失败")

    # ========== 十连 ==========
    @filter.regex(r"^十连$")
    async def multi_gacha(self, event: AstrMessageEvent):
        if not self.gacha:
            yield event.plain_result("❌ 抽卡模块未初始化")
            return
        try:
            uid = event.get_sender_id()
            uname = event.get_sender_name() or str(uid)
            results = self.gacha.multi_gacha(uid, 10, uname)
            lines = "\n".join(results)
            yield event.plain_result(f"@{uname}\n{lines}")
        except Exception as e:
            logger.error(f"十连报错: {e}")
            yield event.plain_result("❌ 抽卡失败")

    # ========== 节气查询 ==========
    @filter.regex(r"^(节气|我的卡牌)$")
    async def show_cards(self, event: AstrMessageEvent):
        if not self.db:
            yield event.plain_result("❌ 插件未初始化")
            return
        try:
            uid = event.get_sender_id()
            uname = event.get_sender_name() or str(uid)
            cards = self.db.get_cards(uid)
            sets = self.db.get_sets_completed(uid)
            bonus = sets * self.config.set_bonus_interest * 100

            spring = " | ".join([f"{t}:{cards[t]}" for t in SOLAR_TERMS_SPRING])
            summer = " | ".join([f"{t}:{cards[t]}" for t in SOLAR_TERMS_SUMMER])
            autumn = " | ".join([f"{t}:{cards[t]}" for t in SOLAR_TERMS_AUTUMN])
            winter = " | ".join([f"{t}:{cards[t]}" for t in SOLAR_TERMS_WINTER])

            msg = f"🀄 已集齐 {sets} 套 | 收益加成 {bonus:.0f}%\n"
            msg += f"🌸春 {spring}\n"
            msg += f"🌻夏 {summer}\n"
            msg += f"🍂秋 {autumn}\n"
            msg += f"❄️冬 {winter}"
            yield event.plain_result(f"@{uname}\n{msg}")
        except Exception as e:
            logger.error(f"节气查询报错: {e}")
            yield event.plain_result("❌ 查询失败")

    # ========== 银行存款 ==========
    @filter.regex(r"^存款\s*(\d+)$")
    async def deposit(self, event: AstrMessageEvent):
        if not self.bank or not self.config.bank_enabled:
            yield event.plain_result("❌ 银行系统已关闭")
            return
        try:
            m = re.search(r"存款\s*(\d+)", event.message_str.strip())
            if not m:
                yield event.plain_result("❌ 格式：存款 <数量>")
                return
            amount = int(m.group(1))
            uid = event.get_sender_id()
            result = self.bank.deposit(uid, amount)
            yield event.plain_result(result)
        except Exception as e:
            logger.error(f"存款报错: {e}")
            yield event.plain_result("❌ 存款失败")

    @filter.regex(r"^取款\s*(\d+)$")
    async def withdraw_first(self, event: AstrMessageEvent):
        """取款第一次确认"""
        if not self.bank or not self.config.bank_enabled:
            yield event.plain_result("❌ 银行系统已关闭")
            return
        try:
            m = re.search(r"取款\s*(\d+)", event.message_str.strip())
            if not m:
                yield event.plain_result("❌ 格式：取款 <序号>（用 存款查询 查看序号）")
                return
            index = int(m.group(1)) - 1
            uid = event.get_sender_id()
            dep, msg = self.bank.check_withdraw(uid, index)
            if dep:
                PENDING_WITHDRAW[uid] = {"index": index, "time": time.time()}
            yield event.plain_result(msg)
        except Exception as e:
            logger.error(f"取款报错: {e}")
            yield event.plain_result("❌ 取款失败")

    @filter.regex(r"^确认取出$")
    async def withdraw_confirm(self, event: AstrMessageEvent):
        """取款第二次确认"""
        if not self.bank or not self.config.bank_enabled:
            yield event.plain_result("❌ 银行系统已关闭")
            return
        uid = event.get_sender_id()
        if uid not in PENDING_WITHDRAW:
            yield event.plain_result("❌ 没有待确认的取款操作，请先使用 取款 <序号>")
            return
        info = PENDING_WITHDRAW[uid]
        if time.time() - info["time"] > 120:
            del PENDING_WITHDRAW[uid]
            yield event.plain_result("⏰ 取款确认已超时，请重新操作")
            return
        result = self.bank.confirm_withdraw(uid, info["index"])
        del PENDING_WITHDRAW[uid]
        yield event.plain_result(result)

    @filter.regex(r"^(利率|存款利率)$")
    async def show_rates(self, event: AstrMessageEvent):
        if not self.bank or not self.config.bank_enabled:
            yield event.plain_result("❌ 银行系统已关闭")
            return
        yield event.plain_result(self.bank.get_interest_rates_display())

    @filter.regex(r"^(存款查询|我的存款)$")
    async def show_deposits(self, event: AstrMessageEvent):
        if not self.bank or not self.config.bank_enabled:
            yield event.plain_result("❌ 银行系统已关闭")
            return
        uid = event.get_sender_id()
        self.bank.check_interest(uid)  # 自动结算利息
        yield event.plain_result(self.bank.get_deposit_info(uid))

    # ========== 管理员命令（不@机器人，直接@成员） ==========
    @filter.regex(r"^@(\d+)\s+(设置|给与|扣除)\s+货币\s+(\d+)$")
    async def admin_currency(self, event: AstrMessageEvent, match):
        uid = event.get_sender_id()
        if not self.config or not self.config.is_admin(uid):
            return
        try:
            target = match.group(1)
            action = match.group(2)
            amount = int(match.group(3))
            if action == "设置":
                self.db.set_balance(target, amount)
                yield event.plain_result(f"✅ 已设置用户 {target} 货币为 {amount}")
            elif action == "给与":
                new_bal = self.db.add_balance(target, amount)
                yield event.plain_result(f"✅ 已给用户 {target} 增加 {amount}，当前余额 {new_bal}")
            elif action == "扣除":
                current = self.db.get_balance(target)
                if current < amount:
                    yield event.plain_result(f"❌ 用户 {target} 余额不足，当前 {current}")
                    return
                new_bal = self.db.add_balance(target, -amount)
                yield event.plain_result(f"✅ 已扣除用户 {target} {amount}，当前余额 {new_bal}")
        except Exception as e:
            logger.error(f"管理员货币操作报错: {e}")
            yield event.plain_result("❌ 操作失败")

    @filter.regex(r"^@(\d+)\s+(设置|给与|扣除)\s+卡牌\s+(\w+)\s+(\d+)$")
    async def admin_cards(self, event: AstrMessageEvent, match):
        uid = event.get_sender_id()
        if not self.config or not self.config.is_admin(uid):
            return
        try:
            target = match.group(1)
            action = match.group(2)
            card_name = match.group(3)
            amount = int(match.group(4))
            if card_name not in SOLAR_TERMS:
                yield event.plain_result(f"❌ 未知卡牌：{card_name}")
                return
            if action == "设置":
                self.db.set_cards(target, card_name, amount)
                yield event.plain_result(f"✅ 已设置 {target} 的 {card_name} 为 {amount}")
            elif action == "给与":
                self.db.add_card(target, card_name, amount)
                new_count = self.db.get_cards(target).get(card_name, 0)
                yield event.plain_result(f"✅ 已给 {target} 增加 {card_name}x{amount}，当前 {new_count}")
            elif action == "扣除":
                cards = self.db.get_cards(target)
                current = cards.get(card_name, 0)
                if current < amount:
                    yield event.plain_result(f"❌ {target} 的 {card_name} 不足，当前 {current}")
                    return
                self.db.add_card(target, card_name, -amount)
                yield event.plain_result(f"✅ 已扣除 {target} 的 {card_name}x{amount}")
        except Exception as e:
            logger.error(f"管理员卡牌操作报错: {e}")
            yield event.plain_result("❌ 操作失败")

    @filter.regex(r"^@(\d+)\s+(设置|给与|扣除)\s+抽卡次数\s+(\d+)$")
    async def admin_tickets(self, event: AstrMessageEvent, match):
        uid = event.get_sender_id()
        if not self.config or not self.config.is_admin(uid):
            return
        try:
            target = match.group(1)
            action = match.group(2)
            amount = int(match.group(3))
            if action == "设置":
                self.db.set_tickets(target, amount)
                yield event.plain_result(f"✅ 已设置 {target} 抽卡次数为 {amount}")
            elif action == "给与":
                new_tickets = self.db.add_tickets(target, amount)
                yield event.plain_result(f"✅ 已给 {target} 增加 {amount} 抽，当前 {new_tickets}")
            elif action == "扣除":
                current = self.db.get_tickets(target)
                if current < amount:
                    yield event.plain_result(f"❌ {target} 抽卡次数不足，当前 {current}")
                    return
                self.db.add_tickets(target, -amount)
                yield event.plain_result(f"✅ 已扣除 {target} {amount} 抽")
        except Exception as e:
            logger.error(f"管理员抽卡次数操作报错: {e}")
            yield event.plain_result("❌ 操作失败")