import threading
import datetime

import assistants.automover
import assistants.priosorter
import assistants.telegram

ASSISTANTS = {
	'priosorter': assistants.priosorter,
	'automover': assistants.automover,
	'telegram': assistants.telegram,
}


def run_now(assistant, cfg, tmp):
	if assistant in cfg and cfg[assistant]['enabled']:
		ASSISTANTS[assistant].run(tmp['api'], tmp['timezone'], cfg[assistant], tmp.setdefault(assistant, {}))
		cfg[assistant]['last_run'] = datetime.datetime.utcnow()


class Runner:

	def __init__(self, config_manager):
		self.should_shutdown = threading.Event()
		self.config_manager = config_manager

	def run_forever(self):
		self.should_shutdown.clear()
		while not self.should_shutdown.is_set():
			for account in self.config_manager:
				api_synced = False
				with self.config_manager.get(account) as (cfg, tmp):
					if not cfg.get('enabled'):
						continue

					# TODO maybe we should make a copy so we don't hold the lock for the whole duration
					# (although we need to be able to change the cfg...)
					for assistant in ASSISTANTS:
						if assistant in cfg and cfg[assistant]['enabled']:
							if ASSISTANTS[assistant].should_run(tmp['api'], tmp['timezone'], cfg[assistant], tmp.setdefault(assistant, {})):
								if not api_synced:
									tmp['api'].sync()
								print('Run', assistant, 'for', account)
								run_now(assistant, cfg, tmp)
								print('Finished', assistant, 'for', account)

			self.should_shutdown.wait(60)

	def shutdown(self):
		self.should_shutdown.set()
