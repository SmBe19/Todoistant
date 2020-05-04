from datetime import datetime, timedelta

from utils import run_every, run_next_in

INIT_CONFIG = {
	'active': [],
}
CONFIG_VERSION = 1
CONFIG_WHITELIST = [
	'src_project',
]
CONFIG_INT = [
	'src_project',
]
CONFIG_LIST = []


def migrate_config(cfg, old_version):
	pass


should_run = run_every(timedelta(minutes=15))


handle_update = run_next_in(timedelta(seconds=1), {'item:deleted', 'item:completed'})


def run(api, timezone, telegram, cfg, tmp):
	# TODO implement
	pass
