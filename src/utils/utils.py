import logging
import time
from datetime import timezone, datetime, timedelta
from typing import Callable, Set, Dict, List

from todoistapi.hooks import HookData
from todoistapi.projects import Project

logger = logging.getLogger(__name__)


def sync_if_necessary(user: 'user_config.UserConfig'):
    if datetime.utcnow() - user.api_last_sync > timedelta(minutes=10):
        sync_with_retry(user)


def sync_with_retry(user: 'user_config.UserConfig'):
    while True:
        try:
            user.api.sync()
            user.api_last_sync = datetime.utcnow()
            return
        except Exception as e:
            logger.error('Error in sync', exc_info=e)
            time.sleep(1)


def utc_to_local(date: datetime, local_timezone: timezone) -> datetime:
    if date.tzinfo:
        return date.astimezone(local_timezone)
    return date.replace(tzinfo=timezone.utc).astimezone(local_timezone)


def local_to_utc(date: datetime) -> datetime:
    if date.tzinfo:
        return date.astimezone(timezone.utc).replace(tzinfo=None)
    return date


def sort_projects(projects: List[Project]) -> List[Project]:
    id_to_project = {project.id: project for project in projects}

    def get_sort_key(project: Project) -> List[int]:
        if project.parent_id:
            return get_sort_key(id_to_project[project.parent_id]) + [project.child_order]
        return [project.child_order]

    return sorted(projects, key=get_sort_key)


def parse_task_config(content: str) -> (str, Dict[str, str]):
    pattern = '[ ]('
    pos = content.find(pattern)
    if pos < 0:
        pattern = '!!('
        pos = content.find(pattern)
        if pos < 0:
            return content, {}
    endpos = content[pos:].find(')')
    if endpos < 0:
        return content, {}
    res = {}
    config = content[pos + len(pattern):pos + endpos]
    for item in config.split(','):
        if ':' in item:
            parts = item.split(':', 1)
            res[parts[0].strip()] = parts[1].strip()
    return content[:pos].strip(), res


def run_every(delta: timedelta) -> Callable:
    def should_run(self, user: 'user_config.UserConfig') -> bool:
        cfg = user.acfg(self)
        if 'last_run' not in cfg:
            return True
        if 'next_run' in cfg and cfg['next_run'] and datetime.utcnow() > cfg['next_run']:
            cfg['next_run'] = None
            return True
        if (datetime.utcnow() - cfg['last_run']) > delta:
            return True
        return False

    return should_run


def run_next_in(delta: timedelta, update_types: Set[str] = None) -> Callable:
    def handle_update(self, user: 'user_config.UserConfig', update: HookData) -> bool:
        cfg = user.acfg(self)
        if update_types is not None and update.data['event_name'] not in update_types:
            return False
        new_next_run = datetime.utcnow() + delta
        if 'next_run' in cfg and cfg['next_run'] and new_next_run > cfg['next_run'] > datetime.utcnow():
            return False
        cfg['next_run'] = new_next_run
        return True

    return handle_update
