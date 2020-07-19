import datetime
import logging
import os
import socketserver
import threading
import time
from logging.handlers import RotatingFileHandler

import dotenv

import my_json
import runner
import server_handlers
import telegram
import todoist_api
from config import ConfigManager
from consts import SOCKET_NAME, CACHE_PATH, CONFIG_PATH

dotenv.load_dotenv('secrets.env')

logging.basicConfig(
	handlers=[RotatingFileHandler('todoistant.log', maxBytes=1000000, backupCount=10)],
	format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
	level=logging.DEBUG
)
stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.INFO)
logging.getLogger().addHandler(stream_handler)
logger = logging.getLogger(__name__)

config_manager = ConfigManager()


class RequestHandler(socketserver.StreamRequestHandler):

	def handle(self):
		for line in self.rfile:
			if not line:
				continue
			try:
				data = my_json.loads(line.strip())
			except ValueError as e:
				logger.warning('Invalid Request', e)
				continue
			if data['cmd'] in server_handlers.handlers:
				res = server_handlers.handlers[data['cmd']](*data.get('args', []), **data.get('kwargs', {}), mgr=config_manager)
				self.wfile.write((my_json.dumps(res) + '\n').encode())


class ThreadingServer(socketserver.UnixStreamServer, socketserver.ThreadingMixIn):
	pass


def run_server(args):
	if os.path.exists(SOCKET_NAME):
		os.remove(SOCKET_NAME)
	if not os.path.isdir(CACHE_PATH):
		os.mkdir(CACHE_PATH)
	if not os.path.exists(CONFIG_PATH):
		os.mkdir(CONFIG_PATH)

	logger.info('Load config...')
	for file in os.listdir(CONFIG_PATH):
		if file.endswith('.json'):
			account = config_manager.get(file[:-5])
			account.load()
			with account as (cfg, tmp):
				if cfg['enabled']:
					tmp['api'], tmp['timezone'] = todoist_api.get_api(cfg['token'])
					tmp['api_last_sync'] = datetime.datetime.utcnow()
				for assistant in runner.ASSISTANTS:
					assist = runner.ASSISTANTS[assistant]
					if assistant in cfg and cfg[assistant]['config_version'] < assist.CONFIG_VERSION:
						assist.migrate_config(cfg[assistant], cfg[assistant]['config_version'])
						cfg[assistant]['config_version'] = assist.CONFIG_VERSION

	logger.info('Config loaded')

	logger.info('Starting server...')
	server = ThreadingServer(SOCKET_NAME, RequestHandler)
	server_thread = threading.Thread(target=server.serve_forever)
	server_thread.daemon = True
	server_thread.start()
	logger.info('Server started')

	logger.info('Starting telegram...')
	my_telegram = telegram.Telegram(config_manager)
	for account in config_manager:
		with config_manager.get(account) as (cfg, tmp):
			if 'telegram' in cfg and cfg['telegram']['chatid'] > 0:
				my_telegram.chat_to_user[cfg['telegram']['chatid']] = account
	telegram_thread = threading.Thread(target=my_telegram.run_forever)
	telegram_thread.daemon = True
	telegram_thread.start()
	config_manager.dummy_configs.add('telegram')
	with config_manager.get('telegram') as (cfg, tmp):
		tmp['telegram'] = my_telegram
	logger.info('Telegram started')

	logger.info('Starting runner...')
	my_runner = runner.Runner(config_manager)
	runner_thread = threading.Thread(target=my_runner.run_forever)
	runner_thread.daemon = True
	runner_thread.start()
	config_manager.dummy_configs.add('todoist')
	with config_manager.get('todoist') as (cfg, tmp):
		tmp['todoist'] = my_runner
	logger.info('Runner started')

	try:
		while True:
			time.sleep(64)
	except KeyboardInterrupt:
		pass
	finally:
		logger.info('Shutting down runner...')
		my_runner.shutdown()
		logger.info('Runner shutdown')
		logger.info('Shutting down telegram...')
		my_telegram.shutdown()
		logger.info('Telegram shutdown')
		logger.info('Shutting down server...')
		server.shutdown()
		logger.info('Server shutdown')
