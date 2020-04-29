import argparse
import getpass
import json
import socket

import runner
import server


def prepare_parser(subparsers: argparse._SubParsersAction):
	add_account = subparsers.add_parser('add_account')
	add_account.set_defaults(func=run_add_account)
	add_account.add_argument('token', nargs='?', default='', help='API token to access account')

	enable = subparsers.add_parser('enable')
	enable.set_defaults(func=run_set_enable)
	enable.add_argument('account', help='Account ID')
	enable.add_argument('assistant', choices=runner.ASSISTANTS.keys(), help='Name of assistant')
	enable.add_argument('enabled', choices=['true', 'false'], help='Whether to enable or disable')


def run_add_account(args):
	client = Client()
	token = args.token or getpass.getpass('Token: ')
	print(client.add_account(token))


def run_set_enable(args):
	client = Client()
	print(client.set_enabled(args.account, args.assistant, args.enabled == 'true'))


class Client:

	def __init__(self):
		self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
		self.socket.connect(server.SOCKET_NAME)
		self.rfile = self.socket.makefile('rb')
		self.wfile = self.socket.makefile('wb')

	def close(self):
		self.rfile.close()
		self.wfile.close()
		self.socket.close()

	def __getattr__(self, item):
		def func(*args, **kwargs):
			call = {
				'cmd': item,
				'args': args,
				'kwargs': kwargs,
			}
			self.wfile.write((json.dumps(call) + '\n').encode())
			self.wfile.flush()
			return json.loads(self.rfile.readline().decode())
		return func
