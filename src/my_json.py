from datetime import datetime
import json

from config import ChangeList


def json_object_hook(o):
	if '__datetime__' in o:
		return datetime.fromisoformat(o['value'])
		# python3.6 does not yet support fromisoformat
		# return datetime.strptime(o['value'], '%Y-%m-%dT%H:%M:%S.%f')
	return o


def json_default(o):
	from config import ChangeDict
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


def load(f):
	return json.load(f, object_hook=json_object_hook)


def loads(s):
	return json.loads(s, object_hook=json_object_hook)


def dump(obj, f):
	json.dump(obj, f, default=json_default)


def dumps(obj):
	return json.dumps(obj, default=json_default)
