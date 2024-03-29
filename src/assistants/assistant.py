from abc import ABC, abstractmethod
from typing import Dict, Iterable, Callable

from config import config, user_config
from todoistapi.hooks import HookData


class Assistant(ABC):

    def __repr__(self) -> str:
        return self.get_id()

    @abstractmethod
    def get_id(self) -> str:
        pass

    @abstractmethod
    def should_run(self, user: 'user_config.UserConfig') -> bool:
        pass

    @abstractmethod
    def handle_update(self, user: 'user_config.UserConfig', update: HookData) -> bool:
        pass

    @abstractmethod
    def run(self, user: 'user_config.UserConfig', send_telegram: Callable[[str], None]) -> None:
        pass

    def get_config_version(self) -> int:
        return 1

    def migrate_config(self, user: 'user_config.UserConfig', cfg: 'config.ChangeDict', old_version: int) -> None:
        pass

    def get_init_config(self) -> Dict[str, object]:
        return {}

    def get_config_allowed_keys(self) -> Iterable[str]:
        return []

    def contains_int_value(self, key: str) -> bool:
        return False

    def contains_list_value(self, key: str) -> bool:
        return False
