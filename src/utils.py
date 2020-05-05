from datetime import timezone, datetime, timedelta


def utc_to_local(date, local_timezone):
	if date.tzinfo:
		return date.astimezone(local_timezone)
	return date.replace(tzinfo=timezone.utc).astimezone(local_timezone)


def local_to_utc(date):
	if date.tzinfo:
		return date.astimezone(timezone.utc).replace(tzinfo=None)
	return date


def parse_task_config(content):
	pattern = '[ ]('
	pos = content.find('[ ](')
	if pos < 0:
		pattern = '!!('
		pos = content.find('!!(')
		if pos < 0:
			return content, {}
	endpos = content[pos:].find(')')
	if endpos < 0:
		return content, {}
	res = {}
	config = content[pos+len(pattern):pos + endpos]
	for item in config.split(','):
		if ':' in item:
			parts = item.split(':', 1)
			res[parts[0].strip()] = parts[1].strip()
	return content[:pos].strip(), res


def run_every(delta):
	def f(api, timezone, cfg, tmp):
		if 'last_run' not in cfg:
			return True
		if 'next_run' in cfg and cfg['next_run'] and datetime.utcnow() > cfg['next_run']:
			cfg['next_run'] = None
			return True
		if (datetime.utcnow() - cfg['last_run']) > delta:
			return True
		return False
	return f


def run_next_in(delta, update_types=None):
	def f(api, timezone, cfg, tmp, update):
		if update_types is not None and update['event_name'] not in update_types:
			return
		new_next_run = datetime.utcnow() + delta
		if 'next_run' in cfg and cfg['next_run'] and new_next_run > cfg['next_run'] > datetime.utcnow():
			return False
		cfg['next_run'] = new_next_run
		return True
	return f
