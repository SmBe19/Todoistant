INIT_CONFIG = {
	'chat_id': 0,
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
	return False


def run(api, timezone, cfg, tmp):
	pass
