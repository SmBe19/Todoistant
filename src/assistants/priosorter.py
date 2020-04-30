from datetime import datetime, timedelta

INIT_CONFIG = {}
CONFIG_VERSION = 1
CONFIG_WHITELIST = []
CONFIG_INT = []
CONFIG_LIST = []


def migrate_config(cfg, old_version):
	pass


def should_run(api, timezone, cfg, tmp):
	return 'last_run' not in cfg or (datetime.utcnow() - cfg['last_run']) > timedelta(minutes=15)


def _sort_key(prio_labels):
	def _func(item):
		day_order = item['day_order']
		prio_order = 0
		if day_order < 0:
			day_order = 10**9
		for label in item['labels']:
			if label in prio_labels:
				prio_order = prio_labels[label]
				break
		return -prio_order, day_order
	return _func


def run(api, timezone, telegram, cfg, tmp):
	prio_labels = {}
	for label in api.state['labels']:
		if label['name'].startswith('prio'):
			try:
				value = int(label['name'][len('prio'):])
				prio_labels[label['id']] = value
			except ValueError:
				pass

	now = datetime.now(timezone)
	items = []
	for item in api.state['items']:
		if not item['due'] or item['date_completed']:
			continue
		due = datetime.strptime(item['due']['date'].split('T')[0], '%Y-%m-%d')
		if now.date() == due.date():
			if str(item['id']) in api.state['day_orders']:
				item.update(day_order=api.state['day_orders'][str(item['id'])])
			items.append(item)
	items.sort(key=_sort_key(prio_labels))
	new_item_day_order = {}
	for idx, item in enumerate(items):
		new_item_day_order[item['id']] = idx+1
	api.items.update_day_orders(new_item_day_order)
	api.commit()
