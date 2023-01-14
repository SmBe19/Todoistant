import datetime
import json
import logging
import os
import traceback
import uuid
from typing import Dict, List, Any, Union

import requests

from todoistapi.items import ItemManager
from todoistapi.labels import LabelManager
from todoistapi.projects import ProjectManager
from todoistapi.user import User
from utils.consts import CACHE_PATH

logger = logging.getLogger(__name__)

RESOURCE_TYPES = '["user", "projects", "labels", "items", "day_orders"]'


# noinspection PyProtectedMember
class TodoistAPI:

    def __init__(self, token: str, cache_dir: str) -> None:
        self._successful_sync: bool = False
        self._token: str = token
        self._cache_dir: str = cache_dir
        self._sync_token: str = '*'
        self._command_queue: List[Dict[str, Any]] = []
        self._session: requests.Session = requests.Session()

        self.user = User()
        self._day_orders = {}
        self.items = ItemManager(self)
        self.projects = ProjectManager(self)
        self.labels = LabelManager(self)

        self._load_cache()

    def _sync(self, commands: List[Dict[str, Any]] = None, resource_types: str = None) -> None:
        data = {
            'sync_token': self._sync_token,
            'resource_types': resource_types or RESOURCE_TYPES,
        }
        if commands:
            data['commands'] = json.dumps(commands)
            logger.debug('Execute Todoist commands: %s', commands)
        result = self._session.post(
            'https://api.todoist.com/sync/v9/sync',
            data=data,
            headers={
                'Authorization': f'Bearer {self._token}',
                'Content-Type': 'application/x-www-form-urlencoded',
            }
        )
        if result.status_code != 200:
            logger.error('Failed to sync with Todoist: %s', result.text)
            return

        parsed = result.json()
        self._sync_token = parsed['sync_token']
        for status_key in parsed.get('sync_status', []):
            if parsed['sync_status'][status_key] != 'ok':
                logger.warning('Todoist command %s failed: %s', status_key, parsed['sync_status'][status_key])
                traceback.print_stack()
        self.user._update(parsed.get('user'))
        if parsed.get('day_orders'):
            self._day_orders.update(parsed.get('day_orders'))
        self.items._update(parsed.get('items'), parsed.get('temp_id_mapping'))
        self.projects._update(parsed.get('projects'), parsed.get('temp_id_mapping'))
        self.labels._update(parsed.get('labels'), parsed.get('temp_id_mapping'))
        # We might only receive the new day_orders dict, but not an update for all items
        for id, order in parsed.get('day_orders', {}).items():
            item = self.items.get_by_id(id)
            if item:
                item._data['day_order'] = order
        self._save_cache()
        self._successful_sync = True

    def _enqueue_command(self, command_type: str, args: Dict[str, Any]) -> Union[str, None]:
        command_id = str(uuid.uuid4())
        command = {
            'type': command_type,
            'args': args,
            'uuid': command_id,
        }
        item_id = None
        if command_type.endswith('_add'):
            item_id = str(uuid.uuid4())
            command['temp_id'] = item_id
        self._command_queue.append(command)
        return item_id

    def _load_cache(self) -> None:
        if not self._cache_dir:
            return
        logger.info('Load API cache...')
        cache_file = os.path.join(self._cache_dir, f'{self._token}.json')
        cache_sync_file = os.path.join(self._cache_dir, f'{self._token}.sync')
        if os.path.isfile(cache_file):
            with open(cache_file) as f:
                cache = json.load(f)
                self.user._load_cache(cache.get('user'))
                self._day_orders.update(cache.get('day_orders'))
                self.items._load_cache(cache.get('items'))
                self.projects._load_cache(cache.get('projects'))
                self.labels._load_cache(cache.get('labels'))
            # If there is a sync file but no cache file we want to perform a full sync
            if os.path.isfile(cache_sync_file):
                with open(cache_sync_file) as f:
                    self._sync_token = f.readline().strip()
            logger.info('API cache for user %s loaded', self.user.id)
        else:
            logger.info('No API cache available')

    def _save_cache(self) -> None:
        if not self._cache_dir:
            return
        logger.debug('Save API cache for user %s', self.user.id)
        to_save = {
            'user': self.user._dump_cache(),
            'day_orders': self._day_orders,
            'items': self.items._dump_cache(),
            'projects': self.projects._dump_cache(),
            'labels': self.labels._dump_cache(),
        }
        with open(os.path.join(self._cache_dir, f'{self._token}.json'), 'w') as f:
            json.dump(to_save, f)
        with open(os.path.join(self._cache_dir, f'{self._token}.sync'), 'w') as f:
            print(self._sync_token, file=f)

    def commit(self) -> None:
        for start in range(0, len(self._command_queue), 99):
            self._sync(self._command_queue[start:start + 99])
        self._command_queue.clear()

    def abort(self) -> None:
        self._command_queue.clear()

    def sync(self) -> None:
        self._sync()

    def sync_user_info(self) -> None:
        self._sync(resource_types='["user"]')

    @property
    def timezone(self) -> datetime.timezone:
        return self.user.timezone

    def had_successful_sync(self) -> bool:
        return self._successful_sync


def get_api(token, sync=True, cache=True) -> TodoistAPI:
    api = TodoistAPI(token, f'./{CACHE_PATH}/' if cache else None)
    if sync:
        api.sync()
    return api
