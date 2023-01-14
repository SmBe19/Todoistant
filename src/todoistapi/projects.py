from typing import Type

from todoistapi.mixins import ByIdManager, ApiObject


# noinspection PyProtectedMember
class ProjectManager(ByIdManager['Project']):

    def get_managed_type(self) -> Type:
        return Project


class Project(ApiObject):

    @property
    def name(self) -> str:
        return self._data.get('name')
