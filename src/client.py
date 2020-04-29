import argparse
import getpass
import socket

import my_json
import runner
from consts import SOCKET_NAME


def prepare_parser(subparsers: argparse._SubParsersAction):
	add_account = subparsers.add_parser('add_account')
	add_account.set_defaults(func=run_add_account)
	add_account.add_argument('account', help='Account ID')

	enable_account = subparsers.add_parser('enable_account')
	enable_account.set_defaults(func=run_enable_account)
	enable_account.add_argument('account', help='Account ID')
	enable_account.add_argument('enabled', choices=['true', 'false'], help='Whether to enable or disable')

	set_token = subparsers.add_parser('set_token')
	set_token.set_defaults(func=run_set_token)
	set_token.add_argument('account', help='Account ID')
	set_token.add_argument('token', nargs='?', default='', help='API token to access account')

	enable = subparsers.add_parser('enable')
	enable.set_defaults(func=run_set_enable)
	enable.add_argument('account', help='Account ID')
	enable.add_argument('assistant', choices=runner.ASSISTANTS.keys(), help='Name of assistant')
	enable.add_argument('enabled', choices=['true', 'false'], help='Whether to enable or disable')


def run_add_account(args):
	with Client() as client:
		print(client.add_account(args.account))


def run_enable_account(args):
	with Client() as client:
		print(client.enable_account(args.account, args.enabled == 'true'))


def run_set_token(args):
	token = args.token or getpass.getpass('Token: ')
	with Client() as client:
		print(client.set_token(args.account, token))


def run_set_enable(args):
	with Client() as client:
		print(client.set_enabled(args.account, args.assistant, args.enabled == 'true'))


class Client:

	def __init__(self):
		self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
		self.socket.connect(SOCKET_NAME)
		self.rfile = self.socket.makefile('rb')
		self.wfile = self.socket.makefile('wb')

	def close(self):
		self.rfile.close()
		self.wfile.close()
		self.socket.close()

	def __enter__(self):
		return self

	def __exit__(self, exc_type, exc_val, exc_tb):
		self.close()

	def __getattr__(self, item):
		def func(*args, **kwargs):
			call = {
				'cmd': item,
				'args': args,
				'kwargs': kwargs,
			}
			self.wfile.write((my_json.dumps(call) + '\n').encode())
			self.wfile.flush()
			return my_json.loads(self.rfile.readline().decode())
		return func
