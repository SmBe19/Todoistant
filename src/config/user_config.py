import datetime
from typing import cast, Dict

from assistants import assistant as assistant_mod
from config.assistant_config import AssistantConfig
from config.config import ChangeDict, Config, ConfigManager
from config.config_wrapper import ConfigWrapper
from todoistapi.todoist_api import TodoistAPI


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
        return AssistantConfig(self._cfg[assistant.get_id()])

    @property
    def tmp(self) -> Dict[str, object]:
        return self._tmp

    def atmp(self, assistant: 'assistant_mod.Assistant') -> Dict[str, object]:
        return cast(Dict[str, object], self._tmp.setdefault(assistant.get_id(), {}))

    @property
    def enabled(self) -> bool:
        return self._cfg['enabled']

    @property
    def api(self) -> TodoistAPI:
        return cast(TodoistAPI, self._tmp['api'])

    @property
    def timezone(self) -> datetime.timezone:
        if 'timezone' not in self._tmp:
            return datetime.timezone.utc
        return cast(datetime.timezone, self._tmp['timezone'])

    @property
    def token(self) -> str:
        return self._cfg['token']

    @property
    def api_last_sync(self) -> datetime.datetime:
        return cast(datetime.datetime, self._tmp['api_last_sync'])

    @api_last_sync.setter
    def api_last_sync(self, value: datetime.datetime) -> None:
        self._tmp['api_last_sync'] = value
