from abc import ABC, abstractmethod
from typing import TypeVar, Generic, Dict, List, Any, Type, Iterator, Union

from todoistapi import todoist_api

T = TypeVar('T', bound='ApiObject')


# noinspection PyProtectedMember
class ByIdManager(ABC, Generic[T]):

    def __init__(self, api: 'todoist_api.TodoistAPI'):
        self._api: 'todoist_api.TodoistAPI' = api
        self._by_id: Dict[str, T] = {}

    @abstractmethod
    def get_managed_type(self) -> Type:
        pass

    def _update(self, new_items: List[Any], temp_id_mapping: Dict[str, str] = None) -> None:
        if temp_id_mapping:
            for key in temp_id_mapping:
                if key in self._by_id:
                    self._by_id[key]._data['id'] = temp_id_mapping[key]
                    self._by_id[temp_id_mapping[key]] = self._by_id[key]
                    del self._by_id[key]
        if not new_items:
            return
        for item in new_items:
            self._by_id.setdefault(item['id'], self.get_managed_type()(self._api))._update(item)

    def _dump_cache(self) -> List[Dict[str, Any]]:
        return [
            item._dump_cache() for item in self
        ]

    def _load_cache(self, data: List[Dict[str, Any]]) -> None:
        self._update(data)

    def __iter__(self) -> Iterator[T]:
        return iter(self._by_id.values())

    def get_by_id(self, id: str) -> Union[None, T]:
        return self._by_id.get(id)


class ApiObject(ABC):

    def __init__(self, api: 'todoist_api.TodoistAPI', data: Dict[str, Any] = None):
        self._api: 'todoist_api.TodoistAPI' = api
        self._data: Dict[str, Any] = data or {}

    def _update(self, new_data: Dict[str, Any]):
        self._data.update(new_data)

    def _dump_cache(self) -> Dict[str, Any]:
        return self._data

    @property
    def id(self) -> str:
        return self._data['id']
