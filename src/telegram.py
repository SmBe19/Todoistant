import base64
import os
import threading
from datetime import datetime, timedelta

import requests

import my_json
import runner


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
			'/project': self.cmd_project,
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
		self.reply(message, 'Hi {}!\n\nRegister your account by going to https://todoistant.smeanox.com and then using /register with the specified id.'.format(message['chat']['first_name']))

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

	@help('Change the project of the last task')
	def cmd_project(self, message):
		if message['chat']['id'] not in self.chat_to_user:
			return self.reply(message, 'Sorry, you need to register to chat with me.')
		with self.config_manager.get(self.chat_to_user[message['chat']['id']]) as (cfg, tmp):
			if 'telegram_last_task' not in tmp:
				return self.reply(message, 'No task was added so far.')
			if datetime.utcnow() - tmp['api_last_sync'] > timedelta(minutes=10):
				tmp['api'].sync()
			project_buttons = [
				{
					'text': project['name'],
					'callback_data': my_json.dumps({
						'cmd': 'project',
						'project': project['id'],
					}),
				} for project in tmp['api']['projects']]
			inline_keyboard = []
			for i in range(0, len(project_buttons)+1, 2):
				inline_keyboard.append(project_buttons[i:i+2])
			self.post('sendMessage', chat_id=message['chat']['id'], text='Choose project', reply_markup={
				'inline_keyboard': inline_keyboard
			})

	def handle_normal_message(self, message):
		chatid = message['chat']['id']
		userid = self.chat_to_user[chatid]
		link = None
		if 'entities' in message:
			for entity in message['entities']:
				if entity['type'] == 'url':
					link = message['text'][entity['offset']:entity['offset']+entity['length']]
					break

		def handle_message(kind, prefix=''):
			with self.config_manager.get(userid) as (cfg, tmp):
				if 'telegram' not in cfg or not cfg['telegram']['enabled']:
					self.reply(message, 'Telegram is disabled for your account. Please enable it to chat with me.')
					return
				if kind + '_project' not in cfg['telegram']:
					self.reply(message, 'Sorry, I don\'t know how to handle this type of message.')
					return
				tmp['api'].sync()
				new_task = tmp['api'].items.add(prefix + message['text'], project_id=cfg['telegram'][kind + '_project'])
				new_task.update(labels=cfg['telegram'][kind + '_labels'][:])
				new_task.update(due={'string': 'today'})
				tmp['api'].commit()
				runner.run_now('priosorter', cfg, tmp)
				tmp['telegram_last_task'] = new_task
				self.reply(message, 'Added task.')

		if 'forward_from' in message or 'forward_sender_name' in message:
			if 'forward_from' in message:
				sender = message['forward_from']
				if 'last_name' in sender:
					sender_name = '{} {}'.format(sender['first_name'], sender['last_name'])
				else:
					sender_name = sender['first_name']
			else:
				sender_name = message['forward_sender_name']
			handle_message('forward', '{}: '.format(sender_name))
		elif link:
			handle_message('link')
		else:
			handle_message('plain')
		self.post('deleteMessage', chat_id=chatid, message_id=message['message_id'])

	def process(self, message):
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
		if message['chat']['id'] not in self.chat_to_user:
			return self.reply(message, 'Sorry, you need to register to chat with me.')
		self.handle_normal_message(message)

	def process_inline(self, query):
		self.post('answerCallbackQuery', callback_query_id=query['id'])
		message = query['message']
		chatid = message['chat']['id']
		if chatid not in self.chat_to_user:
			return
		userid = self.chat_to_user[chatid]
		try:
			data = my_json.loads(query['data'])
		except Exception:
			return
		if data['cmd'] == 'project':
			with self.config_manager.get(userid) as (cfg, tmp):
				if 'telegram_last_task' not in tmp:
					return
				tmp['telegram_last_task'].move(project_id=data['project'])
				tmp['api'].commit()
			self.post('editMessageText', chat_id=chatid, message_id=message['message_id'], text='Task moved.')

	def run_forever(self):
		self.token = base64.urlsafe_b64encode(os.urandom(32)).decode()
		webhook = os.environ['TELEGRAM_WEBHOOK']
		if not webhook.endswith('/'):
			webhook += '/'
		webhook += 'hook/' + self.token
		self.post('setWebhook', url=webhook, max_connections=4, allowed_updates=['message', 'callback_query'])
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
					if 'message' in update:
						try:
							self.process(update['message'])
						except RuntimeError:
							pass
					elif 'callback_query' in update:
						try:
							self.process_inline(update['callback_query'])
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