from typing import Type

from todoistapi.mixins import ByIdManager, ApiObject


# noinspection PyProtectedMember
class SectionManager(ByIdManager['Section']):

    def get_managed_type(self) -> Type:
        return Section


class Section(ApiObject):

    @property
    def name(self) -> str:
        return self._data.get('name')

    @property
    def description(self) -> str:
        return self._data.get('description')

    @property
    def project_id(self) -> str:
        return self._data.get('project_id')

    @property
    def section_order(self) -> int:
        return self._data.get('section_order')
