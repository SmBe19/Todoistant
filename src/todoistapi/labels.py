from typing import Type, Union

from todoistapi.mixins import ByIdManager, ApiObject


# noinspection PyProtectedMember
class LabelManager(ByIdManager['Label']):

    def get_managed_type(self) -> Type:
        return Label

    def get_by_name(self, name: str) -> Union[None, 'Label']:
        for label in self:
            if label.name == name:
                return label
        return None


# noinspection PyProtectedMember
class Label(ApiObject):

    @property
    def name(self) -> str:
        return self._data.get('name')
