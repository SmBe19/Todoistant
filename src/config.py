import logging
import os
import threading

import my_json
from consts import CONFIG_PATH

logger = logging.getLogger(__name__)


class ConfigManager:

	def __init__(self):
		self._lock = threading.Lock()
		self._configs = {}
		self.dummy_configs = set()

	def __contains__(self, item):
		logger.debug('Config Manager check contains %s', item)
		with self._lock:
			return str(item) in self._configs

	def __iter__(self):
		logger.debug('Config Manager iter')
		with self._lock:
			items = [x for x in self._configs.keys() if x not in self.dummy_configs]
		return iter(items)

	def get(self, key):
		logger.debug('Config Manager get %s', key)
		with self._lock:
			key = str(key)
			if key not in self._configs:
				self._configs[key] = Config(key)
			return self._configs[key]


def wrap_in_change(value, root):
	if isinstance(value, dict):
		return ChangeDict(value, root=root)
	elif isinstance(value, list):
		return ChangeList(value, root=root)
	return value


class ChangeDict:

	def __init__(self, data, root=None):
		self._data = data
		self.changed = False
		self._valid = False
		self._root = root or self

		for key in self._data:
			self._data[key] = wrap_in_change(self._data[key], self._root)

	def __contains__(self, item):
		return item in self._data

	def __getitem__(self, item):
		if not self._root._valid:
			raise RuntimeError()
		return self._data[item]

	def get(self, item, default=None):
		if not self._root._valid:
			raise RuntimeError()
		return self._data.get(item, default)

	def __setitem__(self, key, value):
		if not self._root._valid:
			raise RuntimeError()
		if key not in self._data or value != self._data[key]:
			self._root.changed = True
		self._data[key] = wrap_in_change(value, self._root)

	def to_dict(self):
		res = {}
		for key in self._data:
			if isinstance(self._data[key], ChangeDict):
				res[key] = self._data[key].to_dict()
			elif isinstance(self._data[key], ChangeList):
				res[key] = self._data[key].to_dict()
			else:
				res[key] = self._data[key]
		return res


class ChangeList:

	def __init__(self, data, root):
		self._data = data
		self._root = root

		for i in range(len(self._data)):
			self._data[i] = wrap_in_change(self._data[i], self._root)

	def __contains__(self, item):
		return item in self._data

	def __getitem__(self, item):
		if not self._root._valid:
			raise RuntimeError()
		return self._data[item]

	def __setitem__(self, key, value):
		if not self._root._valid:
			raise RuntimeError()
		if value != self._data[key]:
			self._root.changed = True
		self._data[key] = wrap_in_change(value, self._root)

	def append(self, value):
		if not self._root._valid:
			raise RuntimeError()
		self._root.changed = True
		self._data.append(wrap_in_change(value, self._root))

	def to_dict(self):
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

	def __init__(self, key):
		self.key = key
		self._lock = threading.RLock()
		self._data = ChangeDict({})
		self._tmpdata = {}

	def load(self):
		logger.debug('Load config %s', self.key)
		with self._lock:
			with open(os.path.join(CONFIG_PATH, '{}.json'.format(self.key)), 'r') as f:
				self._data = ChangeDict(my_json.load(f))

	def save(self):
		logger.debug('Save config %s', self.key)
		with self._lock:
			with open(os.path.join(CONFIG_PATH, '{}.json'.format(self.key)), 'w') as f:
				my_json.dump(self._data, f)
			self._data.changed = False

	def __enter__(self):
		logger.debug('Config %s acquire lock', self.key)
		self._lock.acquire()
		logger.debug('Config %s acquired lock', self.key)
		self._data._valid = True
		return self._data, self._tmpdata

	def __exit__(self, exc_type, exc_val, exc_tb):
		if self._data.changed:
			self.save()
		self._data._valid = False
		self._lock.release()
		logger.debug('Config %s released lock', self.key)
