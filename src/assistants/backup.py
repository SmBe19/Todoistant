from datetime import datetime
from typing import Callable

from assistants.assistant import Assistant
from config.user_config import UserConfig
from todoistapi.hooks import HookData
from utils.utils import utc_to_local


class Backup(Assistant):

    def get_id(self) -> str:
        return 'backup'

    def should_run(self, user: UserConfig) -> bool:
        cfg = user.acfg(self)
        return not cfg.last_run or \
            utc_to_local(cfg.last_run, user.timezone).date() != datetime.now(user.timezone).date()

    def handle_update(self, user: UserConfig, update: HookData) -> bool:
        return False

    def run(self, user: UserConfig, send_telegram: Callable[[str], None]) -> None:
        user.api.perform_backup()
