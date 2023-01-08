from datetime import datetime, timedelta
from typing import Callable, Any

from assistants.assistant import Assistant
from config.user_config import UserConfig
from utils.utils import run_every, run_next_in


class PrioSorter(Assistant):

    def get_id(self) -> str:
        return 'priosorter'

    should_run = run_every(timedelta(minutes=15))
    handle_update = run_next_in(timedelta(seconds=1), {'item:added', 'item:updated'})

    def run(self, user: UserConfig, send_telegram: Callable[[str], None]) -> None:
        prio_labels = {}
        for label in user.api.state['labels']:
            if label['name'].startswith('prio'):
                try:
                    value = int(label['name'][len('prio'):])
                    prio_labels[label['id']] = value
                except ValueError:
                    pass

        now = datetime.now(user.timezone)
        items = []
        for item in user.api.state['items']:
            if 'due' not in item or not item['due'] or ('date_completed' in item and item['date_completed']):
                continue
            due = datetime.strptime(item['due']['date'].split('T')[0], '%Y-%m-%d')
            if now.date() == due.date():
                if str(item['id']) in user.api.state['day_orders'] and user.api.state['day_orders'][str(item['id'])] != \
                        item[
                            'day_order']:
                    item.update(day_order=user.api.state['day_orders'][str(item['id'])])
                items.append(item)

        def sort_func(cur_item: Any):
            day_order = cur_item['day_order']
            prio_order = 0
            if day_order < 0:
                day_order = 10 ** 9
            for cur_label in cur_item['labels']:
                if cur_label in prio_labels:
                    prio_order = prio_labels[cur_label]
                    break
            return -prio_order, day_order

        items.sort(key=sort_func)
        new_item_day_order = {}
        for idx, item in enumerate(items):
            if item['day_order'] != idx + 1:
                new_item_day_order[item['id']] = idx + 1
        user.api.items.update_day_orders(new_item_day_order)
        user.api.commit()
