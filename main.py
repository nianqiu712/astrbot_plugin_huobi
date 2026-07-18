from pathlib import Path
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api import AstrBotConfig

try:
    from .database import Database
    from .config import Config
    from .admin import AdminCommands
    from .sign import SignModule
    from .fate import FateModule
except ImportError as e:
    logger.error(f"模块导入失败: {e}")
    Database = None
    Config = None
    AdminCommands = None
    SignModule = None
    FateModule = None

@register(
    name="sign_system",
    author="YourName",
    desc="签到+命运+管理员系统，包含货币功能",
    version="1.1.0"
)
class SignSystemPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        logger.info("🚀 开始初始化插件...")

        if Database is None or Config is None:
            logger.error("❌ 核心模块导入失败，插件初始化终止")
            return

        try:
            plugin_dir = Path(__file__).parent
            self.data_dir = plugin_dir / "data"
            self.data_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"✅ 数据目录创建成功: {self.data_dir}")
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
            logger.info(f"✅ Config 初始化成功，管理员: {self.config.admin_qq}")
        except Exception as e:
            logger.error(f"❌ Config 初始化失败: {e}")
            self.config = None

        try:
            if AdminCommands and self.db and self.config:
                self.admin_cmds = AdminCommands(self.db, self.config)
                logger.info("✅ AdminCommands 初始化成功")
            else:
                self.admin_cmds = None
        except Exception as e:
            logger.error(f"❌ AdminCommands 初始化失败: {e}")
            self.admin_cmds = None

        try:
            if SignModule and self.db and self.config:
                self.sign = SignModule(self.db, self.config)
                logger.info("✅ SignModule 初始化成功")
            else:
                self.sign = None
        except Exception as e:
            logger.error(f"❌ SignModule 初始化失败: {e}")
            self.sign = None

        try:
            if FateModule and self.db and self.config:
                self.fate = FateModule(self.db, self.config)
                logger.info("✅ FateModule 初始化成功")
            else:
                self.fate = None
        except Exception as e:
            logger.error(f"❌ FateModule 初始化失败: {e}")
            self.fate = None

        logger.info("🎉 插件初始化完成")

    @filter.command("余额")
    async def my_money(self, event: AstrMessageEvent):
        if not hasattr(self, 'db') or not self.db or not hasattr(self, 'config') or not self.config:
            yield event.plain_result("❌ 插件未正确初始化，无法查询余额")
            return
        try:
            user_id = event.get_sender_id()
            balance = self.db.get_balance(user_id)
            currency_name = getattr(self.config, 'currency_name', '金币')
            yield event.plain_result(f"💰 你的{currency_name}余额：{balance}")
        except Exception as e:
            logger.error(f"查询余额报错: {e}")
            yield event.plain_result("❌ 查询余额失败")

    @filter.regex(r"^(签到|打卡|每日签到)$")
    async def sign_in(self, event: AstrMessageEvent):
        if not self.sign:
            yield event.plain_result("❌ 签到模块未初始化")
            return
        try:
            result = await self.sign.process_sign(event)
            yield event.plain_result(result)
        except Exception as e:
            logger.error(f"签到报错: {e}", exc_info=True)
            yield event.plain_result("❌ 签到失败")

    @filter.regex(r"^命运\s*(\d+)$")
    async def fate_game(self, event: AstrMessageEvent):
        import re
        text = event.message_str.strip()
        m = re.search(r"命运\s*(\d+)", text)
        if not m:
            yield event.plain_result("❌ 命运命令格式错误，例如：命运 100")
            return
        try:
            bet_amount = int(m.group(1))
        except ValueError:
            yield event.plain_result("❌ 请输入有效的数字金额")
            return

        if not self.fate:
            yield event.plain_result("❌ 命运模块未初始化")
            return

        user_id = event.get_sender_id()
        user_name = event.get_sender_name() or str(user_id)
        try:
            result = await self.fate.process_fate(user_id, user_name, bet_amount)
            yield event.plain_result(result)
        except Exception as e:
            logger.error(f"命运玩法报错: {e}", exc_info=True)
            yield event.plain_result("❌ 命运玩法执行失败")

    @filter.regex(r"^/admin\s+(增加|设置|查询)\s+(\d+)\s+(\d+)$")
    async def admin_command(self, event: AstrMessageEvent, match):
        if not self.admin_cmds:
            yield event.plain_result("❌ 管理员模块未初始化")
            return
        try:
            admin_id = event.get_sender_id()
            if not self.config.is_admin(admin_id):
                yield event.plain_result("❌ 你不是管理员，无权操作")
                return

            cmd_type = match.group(1)
            target_user = match.group(2)
            amount = int(match.group(3))
            args = [target_user, amount]

            async for result in self.admin_cmds.handle_admin_command(event, cmd_type, args):
                yield result
        except ValueError:
            yield event.plain_result("❌ 金额必须是数字")
        except Exception as e:
            logger.error(f"管理员命令报错: {e}", exc_info=True)
            yield event.plain_result("❌ 管理员命令执行失败")