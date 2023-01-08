from datetime import datetime, timedelta
from typing import Iterable, Dict, Callable

from assistants.assistant import Assistant
from config.user_config import UserConfig
from utils.utils import parse_task_config, run_every, run_next_in, local_to_utc


class Telegram(Assistant):

    def get_id(self) -> str:
        return 'telegram'

    should_run = run_every(timedelta(minutes=15))
    handle_update = run_next_in(timedelta(seconds=1), {'item:added', 'item:updated'})

    def run(self, user: UserConfig, send_telegram: Callable[[str], None]) -> None:
        telegram_label = None
        for label in user.api.state['labels']:
            if label['name'] == 'telegram':
                telegram_label = label
                break
        if not telegram_label:
            return

        now = datetime.utcnow()
        last = user.acfg(self).last_run or (now - timedelta(days=2))
        next_run = None
        for item in user.api.state['items']:
            if 'date_completed' in item and item['date_completed']:
                continue
            if telegram_label['id'] not in item['labels']:
                continue
            due = local_to_utc(
                datetime.fromisoformat(item['due']['date']).replace(tzinfo=user.timezone)) if 'due' in item and item[
                'due'] else None
            content, config = parse_task_config(item['content'])
            if 'telegram-due' in config:
                new_due = config['telegram-due']
                try:
                    if 'T' in new_due:
                        new_due = datetime.fromisoformat(new_due)
                        if not new_due.tzinfo:
                            new_due = new_due.replace(tzinfo=user.timezone)
                        due = new_due
                    elif ':' in new_due:
                        parts = new_due.split(':')
                        if not due:
                            due = datetime.now(user.timezone)
                        due = due.replace(hour=int(parts[0]), minute=int(parts[1]), second=0, microsecond=0)
                    due = local_to_utc(due)
                except ValueError as e:
                    send_telegram('Error with {}: {}.'.format(content, e))
                    continue
            if not due:
                continue
            if due > now and (not next_run or due < next_run):
                next_run = due
            if last <= due <= now:
                send_telegram(content)
        user.acfg(self).next_run = next_run

    def get_init_config(self) -> Dict[str, object]:
        return {
            'chatid': 0,
            'username': '',
            'plain_labels': [],
            'link_labels': [],
            'forward_labels': [],
        }

    def get_config_allowed_keys(self) -> Iterable[str]:
        return [
            'plain_project',
            'plain_labels',
            'link_project',
            'link_labels',
            'forward_project',
            'forward_labels',
        ]

    def contains_int_value(self, key: str) -> bool:
        return key in {
            'plain_project',
            'plain_labels',
            'link_project',
            'link_labels',
            'forward_project',
            'forward_labels'
        }

    def contains_list_value(self, key: str) -> bool:
        return key in {
            'plain_labels',
            'link_labels',
            'forward_labels'
        }
