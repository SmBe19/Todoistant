import datetime
from typing import cast, Dict, Any

from assistants import assistant as assistant_mod
from config.assistant_config import AssistantConfig
from config.config import ChangeDict, Config, ConfigManager
from config.config_wrapper import ConfigWrapper
from todoistapi import todoist_api


class UserConfig(ConfigWrapper):

    def __init__(self, config: Config) -> None:
        super().__init__(config)

    @staticmethod
    def get(mgr: ConfigManager, key: str) -> 'UserConfig':
        return UserConfig(mgr.get(key))

    @property
    def cfg(self) -> ChangeDict:
        return self._cfg

    def acfg(self, assistant: 'assistant_mod.Assistant') -> AssistantConfig:
        return AssistantConfig(self._cfg.get(assistant.get_id()))

    @property
    def tmp(self) -> Dict[str, Any]:
        return self._tmp

    def atmp(self, assistant: 'assistant_mod.Assistant') -> Dict[str, object]:
        return cast(Dict[str, object], self._tmp.setdefault(assistant.get_id(), {}))

    @property
    def enabled(self) -> bool:
        return self._cfg['enabled']

    @property
    def api(self) -> 'todoist_api.TodoistAPI':
        return cast('todoist_api.TodoistAPI', self._tmp['api'])

    @property
    def timezone(self) -> datetime.timezone:
        return self.api.timezone

    @property
    def token(self) -> str:
        return self._cfg['token']

    @property
    def api_last_sync(self) -> datetime.datetime:
        return cast(datetime.datetime, self._tmp['api_last_sync'])

    @api_last_sync.setter
    def api_last_sync(self, value: datetime.datetime) -> None:
        self._tmp['api_last_sync'] = value
