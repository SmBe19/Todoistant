import base64
import os
import threading
from datetime import datetime, timedelta

import requests


def help(msg):
	def func(f):
		f.__description__ = msg
		return f
	return func


class Telegram:

	def __init__(self, config_manager):
		self.should_shutdown = threading.Event()
		self.new_update = threading.Condition()
		self.config_manager = config_manager
		self.update_queue = []
		self.message_queue = []
		self.processed_updates = set()
		self.chat_to_user = {}
		self.pending_registrations = {}

		self.token = None
		self.bot_token = os.environ['TELEGRAM_TOKEN']
		assert os.environ['TELEGRAM_WEBHOOK']

		self.commands = {
			'/hi': self.cmd_say_hi,
			'/help': self.cmd_help,
			'/register': self.cmd_register,
		}

	def post(self, method, **data):
		if not data:
			data = {}
		res = requests.post('https://api.telegram.org/bot{}/{}'.format(self.bot_token, method), json=data).json()
		if not res['ok']:
			print('Error:', res['description'])
			raise RuntimeError()
		return res['result']

	def reply(self, message, text):
		self.post('sendMessage', chat_id=message['chat']['id'], text=text)

	@help('Start the conversation with your Todoistant')
	def cmd_start(self, message):
		self.reply(message, 'Hi {}!'.format(message['chat']['first_name']))

	@help('Say hi')
	def cmd_say_hi(self, message):
		self.reply(message, 'Hi {}!'.format(message['chat']['first_name']))

	@help('Shows information about the bot')
	def cmd_help(self, message):
		self.reply(message, 'Currently, there is no help available. Sorry.')

	@help('Register your Todoist account')
	def cmd_register(self, message):
		userid = None
		for entity in message['entities']:
			if entity['type'] == 'bot_command':
				userid = message['text'][entity['offset'] + entity['length']:].strip()
		if not userid:
			return self.reply(message, 'Missing User ID')
		try:
			userid = int(userid)
		except ValueError:
			return self.reply(message, 'Invalid User ID')
		code = base64.urlsafe_b64encode(os.urandom(32)).decode()
		self.pending_registrations[code] = (userid, message['chat']['id'], message['chat']['username'], datetime.utcnow())
		self.reply(message, 'Please enter the following code to connect your account:')
		self.reply(message, code)

	def handle_normal_message(self, message):
		pass

	def process(self, message):
		print('process', message)
		if message['chat']['type'] != 'private':
			return self.reply(message, 'This bot is only available in private chats.')
		command = None
		if 'entities' in message:
			for entity in message['entities']:
				if entity['type'] == 'bot_command':
					command = message['text'][entity['offset']:entity['offset']+entity['length']].split('@')[0]
					break
			if command == '/start':
				return self.cmd_start(message)
			if command in self.commands:
				return self.commands[command](message)
		self.handle_normal_message(message)

	def run_forever(self):
		self.token = base64.urlsafe_b64encode(os.urandom(32)).decode()
		webhook = os.environ['TELEGRAM_WEBHOOK']
		if not webhook.endswith('/'):
			webhook += '/'
		webhook += self.token
		self.post('setWebhook', url=webhook, max_connections=4, allowed_updates=['message'])
		self.post('setMyCommands', commands=[{
			'command': cmd,
			'description': func.__description__,
		} for cmd, func in self.commands.items()])
		self.should_shutdown.clear()
		with self.new_update:
			while not self.should_shutdown.is_set():
				while self.update_queue:
					update = self.update_queue.pop()
					if update['update_id'] in self.processed_updates:
						continue
					self.processed_updates.add(update['update_id'])
					if 'message' not in update:
						continue
					try:
						self.process(update['message'])
					except RuntimeError:
						pass
				while self.message_queue:
					chatid, text = self.message_queue.pop()
					try:
						self.post('sendMessage', chat_id=chatid, text=text)
					except RuntimeError:
						pass
				self.new_update.wait(60)

	def receive(self, token, update):
		if token != self.token:
			print('Received bad token')
			return
		with self.new_update:
			self.update_queue.append(update)
			self.new_update.notify_all()

	def send_message(self, receiver, text):
		if not receiver:
			return
		with self.new_update:
			self.message_queue.append((receiver, text))
			self.new_update.notify_all()

	def finish_register(self, account, code):
		if code not in self.pending_registrations:
			return 'invalid code'
		userid, chatid, username, timestamp = self.pending_registrations[code]
		del self.pending_registrations[code]
		if str(userid) != str(account):
			return 'invalid account'
		if (datetime.utcnow() - timestamp) > timedelta(minutes=15):
			return 'expired code'
		with self.config_manager.get(userid) as (cfg, tmp):
			cfg['telegram']['chat_id'] = chatid
			cfg['telegram']['username'] = username
		self.chat_to_user[chatid] = userid
		with self.new_update:
			self.message_queue.append((chatid, 'Successfully connected account!'))
			self.new_update.notify_all()
		return 'ok'

	def shutdown(self):
		self.should_shutdown.set()
		with self.new_update:
			self.new_update.notify_all()
