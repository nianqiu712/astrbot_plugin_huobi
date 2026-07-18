from astrbot.api.event import AstrMessageEvent
from .database import Database
from .config import Config

class AdminCommands:
    def __init__(self, db: Database, config: Config):
        self.db = db
        self.config = config

    async def handle_admin_command(self, event: AstrMessageEvent, sub_cmd: str, args: list):
        user_id = event.get_sender_id()
        if not self.config.is_admin(user_id):
            yield event.plain_result("你没有权限执行此命令。")
            return

        if sub_cmd == "增加":
            if len(args) < 2:
                yield event.plain_result(f"用法：/admin 增加 <用户QQ> <数量>")
                return
            target_id = args[0]
            try:
                amount = int(args[1])
            except ValueError:
                yield event.plain_result("数量必须是数字。")
                return
            new_bal = self.db.add_balance(target_id, amount)
            yield event.plain_result(f"已为用户 {target_id} 增加 {amount} {self.config.currency_name}，当前余额 {new_bal}。")

        elif sub_cmd == "设置":
            if len(args) < 2:
                yield event.plain_result(f"用法：/admin 设置 <用户QQ> <数量>")
                return
            target_id = args[0]
            try:
                amount = int(args[1])
            except ValueError:
                yield event.plain_result("数量必须是数字。")
                return
            self.db.set_balance(target_id, amount)
            yield event.plain_result(f"已设置用户 {target_id} 余额为 {amount} {self.config.currency_name}。")

        elif sub_cmd == "查询":
            if len(args) < 1:
                yield event.plain_result(f"用法：/admin 查询 <用户QQ>")
                return
            target_id = args[0]
            bal = self.db.get_balance(target_id)
            yield event.plain_result(f"用户 {target_id} 的{self.config.currency_name}余额为 {bal}。")

        else:
            yield event.plain_result("未知的管理员命令。可用：增加, 设置, 查询")