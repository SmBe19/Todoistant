import json
import os
import socketserver
import threading
import time

import server_handlers
from config import ConfigManager

SOCKET_NAME = 'todoistant.sock'
CACHE_PATH = 'cache'
CONFIG_PATH = 'config'


def prepare_parser(subparsers):
	server = subparsers.add_parser('server')
	server.set_defaults(func=run_server)


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
			config_manager.get_config(file[:-5]).load()
	print('Config loaded')

	print('Starting server...')
	server = ThreadingServer(SOCKET_NAME, RequestHandler)
	thread = threading.Thread(target=server.serve_forever)
	thread.daemon = True
	thread.start()
	print('Server started')

	try:
		while True:
			time.sleep(64)
	except KeyboardInterrupt:
		print('Shutting down server...')
		server.shutdown()
		print('Server shutdown')
