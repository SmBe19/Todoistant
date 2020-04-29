import threading

import assistants.priosorter
import assistants.automover

ASSISTANTS = {
	'priosorter': assistants.priosorter,
	'automover': assistants.automover,
}


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
					# TODO maybe we should make a copy so we don't hold the lock for the whole duration
					for assistant in ASSISTANTS:
						if assistant in cfg and cfg[assistant]['enabled']:
							if ASSISTANTS[assistant].should_run(tmp['api'], tmp['timezone'], cfg[assistant], tmp.setdefault(assistant, {})):
								if not api_synced:
									tmp['api'].sync()
								print('Run', assistant, 'for', account)
								ASSISTANTS[assistant].run(tmp['api'], tmp['timezone'], cfg[assistant], tmp.setdefault(assistant, {}))
								print('Finished', assistant, 'for', account)

			self.should_shutdown.wait(60)

	def shutdown(self):
		self.should_shutdown.set()
