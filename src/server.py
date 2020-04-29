import json
import os
import socketserver
import threading
import time

import runner
import server_handlers
import todoist_api
from config import ConfigManager
from consts import SOCKET_NAME, CACHE_PATH, CONFIG_PATH

config_manager = ConfigManager()


class RequestHandler(socketserver.StreamRequestHandler):

	def handle(self):
		for line in self.rfile:
			if not line:
				continue
			try:
				data = json.loads(line.strip())
			except ValueError as e:
				print('Invalid Request', e)
				continue
			if data['cmd'] in server_handlers.handlers:
				res = server_handlers.handlers[data['cmd']](*data.get('args', []), **data.get('kwargs', {}), mgr=config_manager)
				self.wfile.write((json.dumps(res) + '\n').encode())


class ThreadingServer(socketserver.UnixStreamServer, socketserver.ThreadingMixIn):
	pass


def run_server(args):
	if os.path.exists(SOCKET_NAME):
		os.remove(SOCKET_NAME)
	if not os.path.isdir(CACHE_PATH):
		os.mkdir(CACHE_PATH)
	if not os.path.exists(CONFIG_PATH):
		os.mkdir(CONFIG_PATH)

	print('Load config...')
	for file in os.listdir(CONFIG_PATH):
		if file.endswith('.json'):
			account = config_manager.get(file[:-5])
			account.load()
			with account as (cfg, tmp):
				tmp['api'], tmp['timezone'] = todoist_api.get_api(cfg['token'])
	print('Config loaded')

	print('Starting server...')
	server = ThreadingServer(SOCKET_NAME, RequestHandler)
	server_thread = threading.Thread(target=server.serve_forever)
	server_thread.daemon = True
	server_thread.start()
	print('Server started')

	print('Starting runner...')
	my_runner = runner.Runner(config_manager)
	runner_thread = threading.Thread(target=my_runner.run_forever)
	runner_thread.daemon = True
	runner_thread.start()
	print('Runner started')

	try:
		while True:
			time.sleep(64)
	except KeyboardInterrupt:
		print('Shutting down server...')
		server.shutdown()
		print('Server shutdown')
		print('Shutting down runner...')
		my_runner.shutdown()
		print('Runner shutdown')
