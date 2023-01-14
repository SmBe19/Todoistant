import dataclasses
import importlib
import json
from datetime import datetime
from typing import Any, Union


def json_object_hook(o: Any) -> Any:
    if '__datetime__' in o:
        return datetime.fromisoformat(o['value'])
    if '__dataclass__' in o:
        module = importlib.import_module(o['__dataclass__'][0])
        klass = getattr(module, o['__dataclass__'][1])
        return klass(**o['value'])
    return o


def json_default(o: Any) -> Any:
    from config.config import ChangeDict, ChangeList
    if isinstance(o, ChangeDict):
        return o.to_dict()
    if isinstance(o, ChangeList):
        return o.to_dict()
    if isinstance(o, datetime):
        return {
            '__datetime__': True,
            'value': o.isoformat()
        }
    if dataclasses.is_dataclass(o):
        return {
            '__dataclass__': [type(o).__module__, type(o).__qualname__],
            'value': dataclasses.asdict(o)
        }
    raise TypeError


def load(f: Any) -> Any:
    return json.load(f, object_hook=json_object_hook)


def loads(s: Union[str, bytes]) -> Any:
    return json.loads(s, object_hook=json_object_hook)


def dump(obj: Any, f: Any) -> None:
    json.dump(obj, f, default=json_default)


def dumps(obj: Any) -> str:
    return json.dumps(obj, default=json_default)
