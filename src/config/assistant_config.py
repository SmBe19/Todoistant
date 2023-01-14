import datetime
from typing import Any, cast

from config.config import ChangeDict


class AssistantConfig:

    def __init__(self, cfg: ChangeDict) -> None:
        self._cfg: ChangeDict = cfg

    def __contains__(self, item: str) -> bool:
        return item in self._cfg

    def __getitem__(self, item: str) -> Any:
        return self._cfg[item]

    def get(self, item: str, default: object = None) -> object:
        return self._cfg.get(item, default)

    def __setitem__(self, key: str, value: object) -> None:
        self._cfg[key] = value

    @property
    def enabled(self) -> bool:
        return bool(self._cfg) and self._cfg['enabled']

    @property
    def last_run(self) -> datetime.datetime:
        return cast(datetime.datetime, self._cfg.get('last_run'))

    @last_run.setter
    def last_run(self, value: datetime.datetime) -> None:
        self._cfg['last_run'] = value

    @property
    def next_run(self) -> datetime.datetime:
        return cast(datetime.datetime, self._cfg.get('next_run'))

    @next_run.setter
    def next_run(self, value: datetime.datetime) -> None:
        self._cfg['next_run'] = value
