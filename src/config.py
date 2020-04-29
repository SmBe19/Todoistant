import json
import os
import threading

import server


class ConfigManager:

	def __init__(self):
		self._lock = threading.Lock()
		self._configs = {}

	def get(self, key):
		with self._lock:
			key = str(key)
			if key not in self._configs:
				self._configs[key] = Config(key)
				self._configs[key].save()
			return self._configs[key]


class ChangeDict:

	def __init__(self, data):
		self._data = data
		self.changed = False

	def __getitem__(self, item):
		return self._data[item]

	def __setitem__(self, key, value):
		if key not in self._data or value != self._data[key]:
			self.changed = True
		self._data[key] = value


class Config:

	def __init__(self, key):
		self.key = key
		self._lock = threading.RLock()
		self._data = ChangeDict({})

	def load(self):
		with self._lock:
			with open(os.path.join(server.CONFIG_PATH, '{}.json'.format(self.key)), 'r') as f:
				self._data = ChangeDict(json.load(f))

	def save(self):
		with self._lock:
			with open(os.path.join(server.CONFIG_PATH, '{}.json'.format(self.key)), 'w') as f:
				json.dump(self._data._data, f)
			self._data.changed = False

	def __enter__(self):
		self._lock.acquire()
		return self._data

	def __exit__(self, exc_type, exc_val, exc_tb):
		if self._data.changed:
			self.save()
		self._lock.release()
