import todoist

import runner
import todoist_api

handlers = {}


def handler(f):
	handlers[f.__name__] = f
	return f


@handler
def add_account(account, mgr):
	if account not in mgr:
		with mgr.get(account) as (cfg, tmp):
			cfg['enabled'] = False
	return 'ok'


@handler
def enable_account(account, enabled, mgr):
	if account not in mgr:
		return 'unknown account'
	with mgr.get(account) as (cfg, tmp):
		if enabled and not cfg['token']:
			return 'can only enable if token is set'
		cfg['enabled'] = enabled


@handler
def set_token(account, token, mgr):
	if account not in mgr:
		return 'unknown account'
	api, timezone = todoist_api.get_api(token)
	if not api.state['user']:
		return 'bad token'
	with mgr.get(account) as (cfg, tmp):
		cfg['enabled'] = True
		cfg['token'] = token
		tmp['api'] = api
		tmp['timezone'] = timezone
	return 'ok'


@handler
def set_enabled(account, assistant, enabled, mgr):
	if assistant not in runner.ASSISTANTS:
		return 'unknown assistant'
	if account not in mgr:
		return 'unknown account'
	with mgr.get(account) as (cfg, tmp):
		if assistant not in cfg:
			cfg[assistant] = runner.ASSISTANTS[assistant].INIT_CONFIG
		cfg[assistant]['enabled'] = enabled
	return 'ok'
