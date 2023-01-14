import datetime
from typing import Any, Dict


class User:
    def __init__(self) -> None:
        self._data = {}

    def _update(self, data: Dict[str, Any]) -> None:
        if not data:
            return
        self._data.update(data)

    def _dump_cache(self) -> Dict[str, Any]:
        return self._data

    def _load_cache(self, data: Dict[str, Any]) -> None:
        self._update(data)

    @property
    def timezone(self) -> datetime.timezone:
        tz_info = self._data['tz_info']
        timezone = datetime.timezone(
            datetime.timedelta(hours=tz_info['hours'], minutes=tz_info['minutes']),
            tz_info['timezone']
        )
        return timezone

    @property
    def id(self) -> str:
        return self._data.get('id')

    @property
    def full_name(self) -> str:
        return self._data.get('full_name')

    @property
    def avatar_big(self) -> str:
        return self._data.get('avatar_big')

    @property
    def tz_info(self) -> Dict[str, Any]:
        return self._data.get('tz_info')
