import logging
import os
import threading
from typing import Iterator, Dict, Set, List, Any

from utils import my_json
from utils.consts import CONFIG_PATH

logger = logging.getLogger(__name__)


class ConfigManager:

    def __init__(self) -> None:
        self._lock: threading.Lock = threading.Lock()
        self._configs: Dict[str, Config] = {}
        self.dummy_configs: Set[str] = set()

    def __contains__(self, item: object) -> bool:
        logger.debug('Config Manager check contains %s', item)
        with self._lock:
            return str(item) in self._configs

    def __iter__(self) -> Iterator[str]:
        logger.debug('Config Manager iter')
        with self._lock:
            items = [x for x in self._configs.keys() if x not in self.dummy_configs]
        return iter(items)

    # TODO replace usages
    def get(self, key: object) -> 'Config':
        logger.debug('Config Manager get %s', key)
        with self._lock:
            key = str(key)
            if key not in self._configs:
                self._configs[key] = Config(key)
            return self._configs[key]


def wrap_in_change(value: object, root: 'ChangeDict') -> object:
    if isinstance(value, dict):
        return ChangeDict(value, root=root)
    if isinstance(value, list):
        return ChangeList(value, root=root)
    if hasattr(value.__class__, '__dataclass_fields__'):
        # TODO handle dataclasses
        return ChangeDict({}, root=root)
    return value


class ChangeDict:

    def __init__(self, data: Dict[str, object], root: 'ChangeDict' = None) -> None:
        self._data: Dict[str, object] = data
        self.changed: bool = False
        self._valid: bool = False
        self._root: ChangeDict = root or self

        for key in self._data:
            self._data[key] = wrap_in_change(self._data[key], self._root)

    def __contains__(self, item: str) -> bool:
        return item in self._data

    def __getitem__(self, item: str) -> Any:
        if not self._root._valid:
            raise RuntimeError()
        return self._data[item]

    def __getattr__(self, item: str) -> Any:
        if not self._root._valid:
            raise RuntimeError()
        return self._data[item]

    def get(self, item: str, default: object = None) -> object:
        if not self._root._valid:
            raise RuntimeError()
        return self._data.get(item, default)

    def __setitem__(self, key: str, value: object) -> None:
        if not self._root._valid:
            raise RuntimeError()
        if key not in self._data or value != self._data[key]:
            self._root.changed = True
        self._data[key] = wrap_in_change(value, self._root)

    def __setattr__(self, key: str, value: object) -> None:
        if key in {'_root', '_data', 'changed', '_valid'}:
            super().__setattr__(key, value)
            return
        if not self._root._valid:
            raise RuntimeError()
        if key not in self._data or value != self._data[key]:
            self._root.changed = True
        self._data[key] = wrap_in_change(value, self._root)

    def to_dict(self) -> Dict[str, object]:
        res = {}
        for key in self._data:
            value = self._data[key]
            if isinstance(value, ChangeDict):
                res[key] = value.to_dict()
            elif isinstance(value, ChangeList):
                res[key] = value.to_dict()
            else:
                res[key] = value
        return res


class ChangeList:

    def __init__(self, data: List[object], root: ChangeDict) -> None:
        self._data: List[object] = data
        self._root: ChangeDict = root

        for i in range(len(self._data)):
            self._data[i] = wrap_in_change(self._data[i], self._root)

    def __contains__(self, item: object) -> bool:
        return item in self._data

    def __getitem__(self, item: int) -> Any:
        if not self._root._valid:
            raise RuntimeError()
        return self._data[item]

    def __setitem__(self, key: int, value: object) -> None:
        if not self._root._valid:
            raise RuntimeError()
        if value != self._data[key]:
            self._root.changed = True
        self._data[key] = wrap_in_change(value, self._root)

    def append(self, value: object) -> None:
        if not self._root._valid:
            raise RuntimeError()
        self._root.changed = True
        self._data.append(wrap_in_change(value, self._root))

    def to_dict(self) -> List[object]:
        res = []
        for i in range(len(self._data)):
            if isinstance(self._data[i], ChangeDict):
                res.append(self._data[i].to_dict())
            elif isinstance(self._data[i], ChangeList):
                res.append(self._data[i].to_dict())
            else:
                res.append(self._data[i])
        return res


class Config:

    def __init__(self, key: str):
        self.key: str = key
        self._lock: threading.RLock = threading.RLock()
        self._data: ChangeDict = ChangeDict({})
        self._tmpdata: Dict[str, object] = {}

    def load(self) -> None:
        logger.debug('Load config %s', self.key)
        with self._lock:
            with open(os.path.join(CONFIG_PATH, '{}.json'.format(self.key)), 'r') as f:
                self._data = ChangeDict(my_json.load(f))

    def save(self) -> None:
        logger.debug('Save config %s', self.key)
        with self._lock:
            with open(os.path.join(CONFIG_PATH, '{}.json'.format(self.key)), 'w') as f:
                my_json.dump(self._data, f)
            self._data.changed = False

    def enter(self) -> (ChangeDict, Dict[str, object]):
        logger.debug('Config %s acquire lock', self.key)
        self._lock.acquire()
        logger.debug('Config %s acquired lock', self.key)
        self._data._valid = True
        return self._data, self._tmpdata

    def exit(self) -> None:
        if self._data.changed:
            self.save()
        self._data._valid = False
        self._lock.release()
        logger.debug('Config %s released lock', self.key)

    def __enter__(self) -> (ChangeDict, Dict[str, object]):
        return self.enter()

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        return self.exit()
