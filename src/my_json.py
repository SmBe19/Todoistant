import datetime
import json


def json_object_hook(o):
	if '__datetime__' in o:
		return datetime.datetime.fromisoformat(o['value'])
	return o


def json_default(o):
	from config import ChangeDict
	if isinstance(o, ChangeDict):
		return o._data
	if isinstance(o, datetime.datetime):
		return {
			'__datetime__': True,
			'value': o.isoformat()
		}
	raise TypeError


def load(f):
	return json.load(f, object_hook=json_object_hook)


def loads(s):
	return json.loads(s, object_hook=json_object_hook)


def dump(obj, f):
	json.dump(obj, f, default=json_default)


def dumps(obj):
	return json.dumps(obj, default=json_default)