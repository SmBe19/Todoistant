import threading
import datetime

import assistants.automover
import assistants.priosorter
import assistants.telegram
import assistants.templates

ASSISTANTS = {
	'priosorter': assistants.priosorter,
	'automover': assistants.automover,
	'telegram': assistants.telegram,
	'templates': assistants.templates,
}


def run_now(assistant, cfg, tmp, mgr):
	def send_message(message):
		if cfg['telegram']['chatid'] <= 0:
			return
		with mgr.get('telegram') as (tcfg, ttmp):
			ttmp['telegram'].send_message(cfg['telegram']['chatid'], message)
	if assistant in cfg and cfg[assistant]['enabled']:
		ASSISTANTS[assistant].run(tmp['api'], tmp['timezone'], send_message, cfg[assistant], tmp.setdefault(assistant, {}))
		cfg[assistant]['last_run'] = datetime.datetime.utcnow()


class Runner:

	def __init__(self, config_manager):
		self.should_shutdown = threading.Event()
		self.new_update = threading.Condition()
		self.config_manager = config_manager
		self.update_queue = []

	def run_forever(self):
		self.should_shutdown.clear()
		with self.new_update:
			while not self.should_shutdown.is_set():
				had_update = False
				while self.update_queue:
					update = self.update_queue.pop()
					userid = update['user_id']
					if userid not in self.config_manager:
						continue
					with self.config_manager.get(userid) as (cfg, tmp):
						for assistant in ASSISTANTS:
							if assistant in cfg and cfg[assistant]['enabled']:
								had_update = ASSISTANTS[assistant].handle_update(tmp['api'], tmp['timezone'], cfg[assistant], tmp.setdefault(assistant, {}), update) or had_update
				if had_update:
					print('Received updates')

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
										tmp['api_last_sync'] = datetime.datetime.utcnow()
									print('Run', assistant, 'for', account)
									run_now(assistant, cfg, tmp, self.config_manager)
									print('Finished', assistant, 'for', account)
				self.new_update.wait(3 if had_update else 60)

	def receive_update(self, update):
		with self.new_update:
			self.update_queue.append(update)
			self.new_update.notify_all()

	def shutdown(self):
		self.should_shutdown.set()
