import json
from datetime import datetime
from typing import Any, Union


def json_object_hook(o: Any) -> Any:
    if '__datetime__' in o:
        return datetime.fromisoformat(o['value'])
    # python3.6 does not yet support fromisoformat
    # return datetime.strptime(o['value'], '%Y-%m-%dT%H:%M:%S.%f')
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
    raise TypeError


def load(f: Any) -> Any:
    return json.load(f, object_hook=json_object_hook)


def loads(s: Union[str, bytes]) -> Any:
    return json.loads(s, object_hook=json_object_hook)


def dump(obj: Any, f: Any) -> None:
    json.dump(obj, f, default=json_default)


def dumps(obj: Any) -> str:
    return json.dumps(obj, default=json_default)
