from abc import ABC
from typing import Dict, Union

from config.config import Config, ChangeDict


# TODO store wrapper in tmp instead of accessing dict
class ConfigWrapper(ABC):

    def __init__(self, config: Config) -> None:
        self._config: Config = config
        self._cfg: Union[ChangeDict, None] = None
        self._tmp: Union[Dict[str, object], None] = None

    def __enter__(self) -> 'ConfigWrapper':
        self._cfg, self._tmp = self._config.enter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self._config.exit()
        self._cfg = None
        self._tmp = None
