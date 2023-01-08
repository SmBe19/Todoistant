import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Iterable, Callable, Any, List, Union

from assistants.assistant import Assistant
from config.user_config import UserConfig
from utils.utils import run_every, run_next_in, parse_task_config

logger = logging.getLogger(__name__)


class ItemDeletedError(Exception):
    pass


class Templates(Assistant):

    def get_id(self) -> str:
        return 'templates'

    # should_run = run_every(timedelta(minutes=15))
    should_run = run_every(timedelta(seconds=15))
    handle_update = run_next_in(timedelta(seconds=1), {'item:deleted', 'item:completed'})

    def run(self, user: UserConfig, send_telegram: Callable[[str], None]) -> None:
        new_active = []
        for template in user.acfg(self)['active']:
            if not template.finished:
                try:
                    logger.debug('Start update_template_state')
                    self._update_template_state(user, template)
                    logger.debug('Finished update_template_state')
                except ItemDeletedError:
                    template.finished = datetime.utcnow()
                    template.status = 'Item was deleted'
                except Exception as e:
                    logger.debug('Template exception', e)
                new_active.append(template)
            else:
                if (datetime.utcnow() - template['finished']) < timedelta(days=3):
                    new_active.append(template)
        user.acfg(self)['active'] = new_active

    # TODO add API typing
    def _parse_template_item(self, user: UserConfig, item: Any) -> 'TemplateItem':
        content, config = parse_task_config(item['content'])
        res = TemplateItem(
            id=config.get('template-id'),
            content=content,
            labels=item['labels'],
            priority=item['priority'],
            due=config.get('template-due', None),
            depends=[x for x in config.get('template-depends', '').split('|') if x],
            children=[],
            item_id=None,
            completed=False,
        )
        for child in user.api.state['items']:
            if child['parent_id'] == item['id']:
                res.children.append(self._parse_template_item(user, child))
        return res

    def _parse_template(self, user: UserConfig, template_id: str, project_id: str) -> 'TemplateInstance':
        items = []
        root_item = user.api.items.get_by_id(template_id)
        project = user.api.projects.get_by_id(project_id)
        for item in user.api.state['items']:
            if item['parent_id'] == template_id:
                items.append(self._parse_template_item(user, item))
        return TemplateInstance(
            template=root_item['content'].rstrip(':'),
            project=project['name'],
            project_id=project_id,
            start=datetime.utcnow(),
            finished=None,
            status='Running',
            items=items,
        )

    def _update_template_state(self, user: UserConfig, template: 'TemplateInstance') -> None:
        completed = set()
        finished = [True]  # we use a list, so we can access it in the function...

        def collect_completed(item: 'TemplateItem'):
            if item.item_id:
                my_item = user.api.items.get_by_id(item.item_id)
                if not my_item:
                    template.status = 'Item was deleted'
                    template.finished = datetime.utcnow()
                    raise ItemDeletedError()
                if my_item['checked'] == 1:
                    completed.add(item.id)
                else:
                    finished[0] = False
            else:
                finished[0] = False
            for child in item.children:
                collect_completed(child)

        for item in template.items:
            collect_completed(item)

        if finished[0]:
            template.finished = datetime.utcnow()
            template.status = 'Finished'
            return

        temp_id_to_task = {}

        def create_new_items(item: 'TemplateItem', parent_id: str = None) -> None:
            if not item.item_id:
                for dependency in item.depends:
                    if dependency not in completed:
                        return
                new_task = user.api.items.add(item.content, project_id=template.project_id, labels=item.labels,
                                              priority=item.priority, parent_id=parent_id)
                if item.due:
                    new_task.update(due={'string': item.duedue, 'lang': 'en'})
                temp_id_to_task[new_task['id']] = new_task
                item.item_id = new_task['id']
            for child in item.children:
                create_new_items(child, item.item_id)

        for item in template.items:
            create_new_items(item)

        user.api.commit()

        def assign_ids(item: 'TemplateItem'):
            if item.item_id in temp_id_to_task:
                item.item_id = temp_id_to_task[item.item_id]['id']
            for child in item.children:
                assign_ids(child)

        for item in template.items:
            assign_ids(item)

    def get_templates(self, user: UserConfig) -> List['TemplateEntry']:
        cfg = user.acfg(self)
        if 'src_project' not in cfg:
            return []
        return [TemplateEntry(
            name=item['content'].rstrip(':'),
            id=item['id'],
        ) for item in user.api.state['items'] if item['project_id'] == cfg['src_project'] and not item['parent_id']]

    def start(self, user: UserConfig, template_id: str, project_id: str):
        try:
            template = self._parse_template(user, template_id, project_id)
        except RuntimeError as e:
            logger.error("Failed to parse template:", e)
            return 'Invalid template'
        try:
            self._update_template_state(user, template)
        except ItemDeletedError:
            return 'Item was deleted ???'
        user.acfg(self)['active'].append(template)
        return 'ok'

    def get_init_config(self) -> Dict[str, object]:
        return {
            'active': [],
        }

    def get_config_allowed_keys(self) -> Iterable[str]:
        return [
            'src_project',
        ]

    def contains_int_value(self, key: str) -> bool:
        return key in {
            'src_project',
        }


@dataclass
class TemplateItem:
    id: str
    content: str
    # TODO add API typing
    labels: List[Any]
    # TODO add API typing
    priority: Any
    due: Union[str, None]
    depends: List[str]
    children: List['TemplateItem']
    item_id: Union[str, None]
    completed: bool


@dataclass
class TemplateInstance:
    template: str
    project: str
    project_id: str
    start: datetime
    finished: Union[datetime, None]
    status: str
    items: List['TemplateItem']


@dataclass
class TemplateEntry:
    name: str
    id: str
