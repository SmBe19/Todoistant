from datetime import datetime, timedelta

from utils import parse_task_config, utc_to_local, run_every

INIT_CONFIG = {}
CONFIG_VERSION = 1
CONFIG_WHITELIST = []
CONFIG_INT = []
CONFIG_LIST = []


def migrate_config(cfg, old_version):
	pass


def should_run(api, timezone, cfg, tmp):
	return 'last_run' not in cfg or utc_to_local(cfg['last_run'], timezone).date() != datetime.now(timezone).date()


def handle_update(api, timezone, cfg, tmp, update):
	return False


def run(api, timezone, telegram, cfg, tmp):
	automove_label = None
	for label in api.state['labels']:
		if label['name'] == 'automove':
			automove_label = label
			break
	if not automove_label:
		return

	now = datetime.now(timezone)
	for item in api.state['items']:
		if not item['due'] or item['date_completed']:
			continue
		if automove_label['id'] not in item['labels']:
			continue
		due = datetime.strptime(item['due']['date'].split('T')[0], '%Y-%m-%d')
		if now.date() > due.date():
			content, config = parse_task_config(item['content'])
			if 'T' in item['due']['date']:
				timepart = 'T' + item['due']['date'].split('T', 1)[1]
			else:
				timepart = ''
			nowstr = now.strftime('%Y-%m-%d')
			if 'automove-by' in config:
				try:
					days = int(config['automove-by']) - 1
					if days > 0:
						nowstr = (now + timedelta(days=days)).strftime('%Y-%m-%d')
				except ValueError as e:
					telegram('Error with {}: {}.'.format(content, e))
					continue
			new_due = item['due']
			new_due['date'] = nowstr + timepart
			item.update(due=new_due)
	api.commit()
