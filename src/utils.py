from datetime import timezone, datetime, timedelta


def utc_to_local(date, local_timezone):
	return date.replace(tzinfo=timezone.utc).astimezone(local_timezone)


def parse_task_config(content):
	pos = content.find('[ ](')
	if pos < 0:
		return content, {}
	endpos = content[pos:].find(')')
	if endpos < 0:
		return content, {}
	res = {}
	config = content[pos+4:pos + endpos]
	for item in config.split(','):
		if ':' in item:
			parts = item.split(':', 1)
			res[parts[0].strip()] = parts[1].strip()
	return content[:pos].strip(), res


def run_every(delta):
	def f(api, timezone, cfg, tmp):
		if 'last_run' not in cfg:
			return True
		if (datetime.utcnow() - cfg['last_run']) > delta:
			return True
		if 'next_run' in cfg and cfg['next_run'] and datetime.now(timezone) > cfg['next_run']:
			cfg['next_run'] = None
			return True
		return False
	return f


def run_next_in(delta, update_types=None):
	def f(api, timezone, cfg, tmp, update):
		if update_types is not None and update['event_name'] not in update_types:
			return
		new_next_run = datetime.now(timezone) + delta
		if 'next_run' in cfg and cfg['next_run'] and new_next_run > cfg['next_run'] > datetime.now(timezone):
			return False
		cfg['next_run'] = new_next_run
		return True
	return f
