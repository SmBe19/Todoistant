import datetime

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
def account_exists(account, mgr):
	return account in mgr


@handler
def enable_account(account, enabled, mgr):
	if account not in mgr:
		return 'unknown account'
	with mgr.get(account) as (cfg, tmp):
		if enabled and not cfg['token']:
			return 'can only enable if token is set'
		cfg['enabled'] = enabled
	return 'ok'


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
		tmp['api_last_sync'] = datetime.datetime.utcnow()
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
			cfg[assistant]['config_version'] = runner.ASSISTANTS[assistant].CONFIG_VERSION
		cfg[assistant]['enabled'] = enabled
	return 'ok'


@handler
def get_config(account, mgr):
	if account not in mgr:
		return None
	with mgr.get(account) as (cfg, tmp):
		cfg_dict = cfg.to_dict()
		del cfg_dict['token']
		return cfg_dict


@handler
def update_config(account, update, mgr):
	if account not in mgr:
		return 'unknown account'

	def do_update(cfg, upd):
		for key in upd:
			if key not in cfg:
				cfg[key] = upd[key]
			elif isinstance(upd[key], dict):
				do_update(cfg[key], upd[key])
			else:
				cfg[key] = upd[key]

	with mgr.get(account) as (cfg, tmp):
		do_update(cfg, update)

	return 'ok'


@handler
def get_projects(account, mgr):
	if account not in mgr:
		return None
	with mgr.get(account) as (cfg, tmp):
		if datetime.datetime.utcnow() - tmp['api_last_sync'] > datetime.timedelta(minutes=10):
			tmp['api'].sync()
		return [{
			'name': project['name'],
			'id': project['id'],
		} for project in tmp['api'].state['projects']]


@handler
def get_labels(account, mgr):
	if account not in mgr:
		return None
	with mgr.get(account) as (cfg, tmp):
		if datetime.datetime.utcnow() - tmp['api_last_sync'] > datetime.timedelta(minutes=10):
			tmp['api'].sync()
		return [{
			'name': project['name'],
			'id': project['id'],
		} for project in tmp['api'].state['labels']]


@handler
def telegram_update(token, update, mgr):
	with mgr.get('telegram') as (cfg, tmp):
		tmp['telegram'].receive(token, update)
	return 'ok'


@handler
def telegram_disconnect(account, mgr):
	if account not in mgr:
		return 'unknown account'

	with mgr.get(account) as (cfg, tmp):
		with mgr.get('telegram') as (tcfg, ttmp):
			ttmp['telegram'].send_message(cfg['telegram']['chat_id'], 'Account was disconnected.')
			del ttmp['telegram'].chat_to_user[cfg['telegram']['chat_id']]
		cfg['telegram']['chat_id'] = 0
		cfg['telegram']['username'] = ''
	return 'ok'


@handler
def telegram_connect(account, code, mgr):
	with mgr.get('telegram') as (cfg, tmp):
		return tmp['telegram'].finish_register(account, code)
