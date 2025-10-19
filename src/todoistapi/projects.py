from typing import Type, Union

from todoistapi.mixins import ByIdManager, ApiObject


# noinspection PyProtectedMember
class ProjectManager(ByIdManager['Project']):

    def get_managed_type(self) -> Type:
        return Project


class Project(ApiObject):

    @property
    def name(self) -> str:
        return self._data.get('name')

    @property
    def child_order(self) -> int:
        return self._data.get('child_order')

    @property
    def parent_id(self) -> Union[None, str]:
        return self._data.get('parent_id')

    @property
    def is_archived(self) -> bool:
        return self._data.get('is_archived', False)
