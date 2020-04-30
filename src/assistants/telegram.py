from datetime import datetime, timedelta

from utils import utc_to_local, parse_task_config

INIT_CONFIG = {
	'chatid': 0,
	'username': '',
}
CONFIG_VERSION = 1
CONFIG_WHITELIST = [
	'plain_project',
	'plain_labels',
	'link_project',
	'link_labels',
	'forward_project',
	'forward_labels',
]
CONFIG_LIST = [
	'plain_labels',
	'link_labels',
	'forward_labels',
]
CONFIG_INT = [
	'plain_project',
	'plain_labels',
	'link_project',
	'link_labels',
	'forward_project',
	'forward_labels',
]


def migrate_config(cfg, old_version):
	pass


def should_run(api, timezone, cfg, tmp):
	return 'last_run' not in cfg or (datetime.utcnow() - cfg['last_run']) > timedelta(minutes=15) or ('next_run' in cfg and cfg['next_run'] and datetime.now(timezone) > cfg['next_run'])


def run(api, timezone, telegram, cfg, tmp):
	telegram_label = None
	for label in api.state['labels']:
		if label['name'] == 'telegram':
			telegram_label = label
			break
	if not telegram_label:
		return

	now = datetime.now(timezone)
	last = utc_to_local(cfg.get('last_run', now - timedelta(days=2)), timezone)
	next_run = None
	for item in api.state['items']:
		if not item['due'] or item['date_completed']:
			continue
		if telegram_label['id'] not in item['labels']:
			continue
		due = datetime.fromisoformat(item['due']['date']).replace(tzinfo=timezone)
		content, config = parse_task_config(item['content'])
		if 'telegram-due' in config:
			new_due = config['telegram-due']
			try:
				if 'T' in new_due:
					new_due = datetime.fromisoformat(new_due)
					if not new_due.tzinfo:
						new_due = new_due.replace(tzinfo=timezone)
					due = new_due
				elif ':' in new_due:
					parts = new_due.split(':')
					due = due.replace(hour=int(parts[0]), minute=int(parts[1]))
			except ValueError as e:
				telegram('Error with {}: {}.'.format(content, e))
				continue
		if due > now and (not next_run or due < next_run):
			next_run = due
		if last <= due <= now:
			telegram(content)
	cfg['next_run'] = next_run
