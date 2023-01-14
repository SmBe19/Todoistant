from datetime import datetime, timedelta
from typing import Callable

from assistants.assistant import Assistant
from config.user_config import UserConfig
from todoistapi.hooks import HookData
from utils.utils import parse_task_config, utc_to_local

LABEL_NAME: str = 'automove'


class AutoMover(Assistant):

    def get_id(self) -> str:
        return 'automover'

    def should_run(self, user: UserConfig) -> bool:
        cfg = user.acfg(self)
        return not cfg.last_run or \
            utc_to_local(cfg.last_run, user.timezone).date() != datetime.now(user.timezone).date()

    def handle_update(self, user: UserConfig, update: HookData) -> bool:
        return False

    def run(self, user: UserConfig, send_telegram: Callable[[str], None]) -> None:
        if not user.api.labels.get_by_name(LABEL_NAME):
            return

        now = datetime.now(user.timezone)
        for item in user.api.items:
            if not item.due.is_set() or item.checked:
                continue
            if LABEL_NAME not in item.labels:
                continue
            due = item.due.parsed_day
            if now.date() > due.date():
                content, config = parse_task_config(item.content)
                if 'T' in item.due.date:
                    timepart = 'T' + item.due.date.split('T', 1)[1]
                else:
                    timepart = ''
                nowstr = now.strftime('%Y-%m-%d')
                if 'automove-by' in config:
                    try:
                        days = int(config['automove-by']) - 1
                        if days > 0:
                            nowstr = (now + timedelta(days=days)).strftime('%Y-%m-%d')
                    except ValueError as e:
                        send_telegram('Error with {}: {}.'.format(content, e))
                        continue
                item.due.date = nowstr + timepart
        user.api.commit()
