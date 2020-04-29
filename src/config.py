import datetime
import json
import os
import threading

import server


class ConfigManager:

	def __init__(self):
		self._lock = threading.Lock()
		self._configs = {}

	def __contains__(self, item):
		with self._lock:
			return item in self._configs

	def __iter__(self):
		return iter(self._configs.keys())

	def get(self, key):
		with self._lock:
			key = str(key)
			if key not in self._configs:
				self._configs[key] = Config(key)
			return self._configs[key]


class ChangeDict:

	def __init__(self, data, root=None):
		self._data = data
		self.changed = False
		self._valid = False
		self._root = root or self

		for key in self._data:
			if isinstance(self._data[key], dict):
				self._data[key] = ChangeDict(self._data[key], root=self._root)

	def __contains__(self, item):
		return item in self._data

	def __getitem__(self, item):
		if not self._root._valid:
			raise RuntimeError()
		return self._data[item]

	def __setitem__(self, key, value):
		if not self._root._valid:
			raise RuntimeError()
		if key not in self._data or value != self._data[key]:
			self._root.changed = True
		if isinstance(value, dict):
			value = ChangeDict(value, root=self._root)
		self._data[key] = value


class Config:

	def __init__(self, key):
		self.key = key
		self._lock = threading.RLock()
		self._data = ChangeDict({})
		self._tmpdata = {}

	def load(self):
		def json_object_hook(o):
			if '__datetime__' in o:
				return datetime.datetime.fromisoformat(o['value'])
			return o

		with self._lock:
			with open(os.path.join(server.CONFIG_PATH, '{}.json'.format(self.key)), 'r') as f:
				self._data = ChangeDict(json.load(f, object_hook=json_object_hook))

	def save(self):
		def json_default(o):
			if isinstance(o, ChangeDict):
				return o._data
			if isinstance(o, datetime.datetime):
				return {
					'__datetime__': True,
					'value': o.isoformat()
				}
			raise TypeError

		with self._lock:
			with open(os.path.join(server.CONFIG_PATH, '{}.json'.format(self.key)), 'w') as f:
				json.dump(self._data, f, default=json_default)
			self._data.changed = False

	def __enter__(self):
		self._lock.acquire()
		self._data._valid = True
		return self._data, self._tmpdata

	def __exit__(self, exc_type, exc_val, exc_tb):
		if self._data.changed:
			self.save()
		self._data._valid = False
		self._lock.release()
