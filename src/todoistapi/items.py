from datetime import datetime
from typing import Type, Dict, Any, List, Union

from todoistapi.mixins import ByIdManager, ApiObject
from utils.utils import local_to_utc


# noinspection PyProtectedMember
class ItemManager(ByIdManager['Item']):

    def get_managed_type(self) -> Type:
        return Item

    def add(self, content: str, **kwargs) -> 'Item':
        data = {'content': content}
        data.update(kwargs)
        new_id = self._api._enqueue_command('item_add', data)
        data['id'] = new_id
        new_item = Item(self._api, data)
        self._by_id[new_id] = new_item
        return new_item

    def update_day_orders(self, new_orders: Dict[str, int]) -> None:
        self._api._enqueue_command('item_update_day_orders', {'ids_to_orders': new_orders})


# noinspection PyProtectedMember
class Item(ApiObject):

    @property
    def content(self) -> str:
        return self._data.get('content')

    @property
    def due(self) -> 'ItemDueDate':
        return ItemDueDate(self, self._data.get('due'))

    @due.setter
    def due(self, value: Dict[str, Any]) -> None:
        self._api._enqueue_command('item_update', {'id': self.id, 'due': value})

    @property
    def checked(self) -> bool:
        return self._data.get('checked', False)

    @property
    def completed_at(self) -> Union[None, str]:
        return self._data.get('completed_at')

    @property
    def priority(self) -> int:
        return self._data.get('priority', 1)

    @property
    def labels(self) -> List[str]:
        return self._data.get('labels', [])

    @labels.setter
    def labels(self, value: List[str]) -> None:
        self._api._enqueue_command('item_update', {'id': self.id, 'labels': value})

    @property
    def day_order(self) -> int:
        return self._data.get('day_order')

    @property
    def child_order(self) -> int:
        return self._data.get('child_order')

    @property
    def parent_id(self) -> Union[None, str]:
        return self._data.get('parent_id')

    @property
    def project_id(self) -> str:
        return self._data.get('project_id')

    def mark_as_complete(self) -> None:
        self._api._enqueue_command('item_close', {'id': self.id})

    def move(self, project_id: str = None, section_id: str = None, parent_id: str = None) -> None:
        if project_id:
            self._api._enqueue_command('item_move', {'id': self.id, 'project_id': project_id})
        elif section_id:
            self._api._enqueue_command('item_move', {'id': self.id, 'section_id': section_id})
        elif parent_id:
            self._api._enqueue_command('item_move', {'id': self.id, 'parent_id': parent_id})


# noinspection PyProtectedMember
class ItemDueDate:

    def __init__(self, item: Item, data: Dict[str, Any]):
        self._item = item
        self._data = data or {}

    def is_set(self) -> bool:
        return 'date' in self._data

    @property
    def date(self) -> Union[None, str]:
        return self._data.get('date')

    @date.setter
    def date(self, value: str) -> None:
        new_due = self._data.copy()
        new_due['date'] = value
        self._item._api._enqueue_command('item_update', {'id': self._item.id, 'due': new_due})

    @property
    def parsed_datetime_local(self) -> Union[None, datetime]:
        date = self.date
        if not date:
            return None
        return datetime.fromisoformat(date).replace(tzinfo=self._item._api.timezone)

    @property
    def parsed_datetime_utc(self) -> Union[None, datetime]:
        parsed = self.parsed_datetime_local
        if not parsed:
            return None
        return local_to_utc(parsed)

    @property
    def parsed_day(self) -> Union[None, datetime]:
        date = self.date
        if not date:
            return None
        return datetime.strptime(date.split('T')[0], '%Y-%m-%d')
