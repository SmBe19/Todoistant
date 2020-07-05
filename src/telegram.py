import base64
import logging
import os
import threading
from datetime import datetime, timedelta
from functools import wraps

import requests

import my_json
import runner
from assistants import templates
from server_handlers import sync_if_necessary
from utils import sync_with_retry

logger = logging.getLogger(__name__)


def help(msg):
	def func(f):
		f.__description__ = msg
		return f
	return func


def require_register(f):
	@wraps(f)
	def wrapper(self, message, *args, **kwargs):
		if message['chat']['id'] not in self.chat_to_user:
			return self.reply(message, 'Sorry, you need to register to chat with me.')
		return f(self, message, *args, **kwargs)
	return wrapper


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
			'/default_project': self.cmd_default_project,
			'/labels': self.cmd_labels,
			'/default_labels': self.cmd_default_labels,
			'/reset': self.cmd_reset_default,
			'/template': self.cmd_template,
		}

	def post(self, method, **data):
		if not data:
			data = {}
		res = requests.post('https://api.telegram.org/bot{}/{}'.format(self.bot_token, method), json=data).json()
		if not res['ok']:
			logger.warning('Error: %s', res['description'])
			raise RuntimeError()
		return res['result']

	def reply(self, message, text):
		self.post('sendMessage', chat_id=message['chat']['id'], text=text)

	def reply_keyboard(self, message, text, buttons):
		self.post('sendMessage', chat_id=message['chat']['id'], text=text, reply_markup={
			'inline_keyboard': buttons
		})

	def change_reply(self, message, text):
		self.post('editMessageText', chat_id=message['chat']['id'], message_id=message['message_id'], text=text)

	def change_keyboard(self, message, text, buttons):
		self.post('editMessageText', chat_id=message['chat']['id'], message_id=message['message_id'], text=text, reply_markup={
			'inline_keyboard': buttons
		})

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

	def buttons_in_rows(self, buttons, rows):
		inline_keyboard = []
		for i in range(0, len(buttons)+rows-1, rows):
			inline_keyboard.append(buttons[i:i+rows])
		return inline_keyboard

	def create_project_buttons(self, tmp, cmd):
		sync_if_necessary(tmp)
		project_buttons = [
			{
				'text': project['name'],
				'callback_data': my_json.dumps({
					'cmd': cmd,
					'project': project['id'],
				}),
			} for project in tmp['api']['projects']]
		return self.buttons_in_rows(project_buttons, 2)

	@help('Change the project of the last task')
	@require_register
	def cmd_project(self, message):
		with self.config_manager.get(self.chat_to_user[message['chat']['id']]) as (cfg, tmp):
			if 'telegram_last_task' not in tmp:
				return self.reply(message, 'No task was added so far.')
			self.reply_keyboard(message, 'Choose project:', self.create_project_buttons(tmp, 'project'))

	@help('Change the default project')
	@require_register
	def cmd_default_project(self, message):
		with self.config_manager.get(self.chat_to_user[message['chat']['id']]) as (cfg, tmp):
			self.reply_keyboard(message, 'Choose default project for next 20 minutes:', self.create_project_buttons(tmp, 'default_project'))

	def create_label_buttons(self, tmp, cmd, active):
		sync_if_necessary(tmp)
		label_buttons = [
			{
				'text': '{} (on)'.format(label['name']) if label['id'] in active else label['name'],
				'callback_data': my_json.dumps({
					'cmd': cmd,
					'label': label['id'],
				}),
			} for label in tmp['api']['labels']]
		label_buttons.append({
			'text': 'Finish.',
			'callback_data': my_json.dumps({
				'cmd': cmd,
				'label': -1,
			}),
		})
		return self.buttons_in_rows(label_buttons, 2)

	@help('Change the labels of the last task')
	@require_register
	def cmd_labels(self, message):
		with self.config_manager.get(self.chat_to_user[message['chat']['id']]) as (cfg, tmp):
			if 'telegram_last_task' not in tmp:
				return self.reply(message, 'No task was added so far.')
			self.reply_keyboard(message, 'Choose labels:', self.create_label_buttons(tmp, 'labels', tmp['telegram_last_task']['labels']))

	@help('Change the default labels')
	@require_register
	def cmd_default_labels(self, message):
		with self.config_manager.get(self.chat_to_user[message['chat']['id']]) as (cfg, tmp):
			if 'telegram_default_labels' not in tmp or self.default_expired(tmp):
				tmp['telegram_default_labels'] = []
			self.reply_keyboard(message, 'Choose default labels for next 20 minutes:', self.create_label_buttons(tmp, 'default_labels', tmp['telegram_default_labels']))

	@help('Reset the default settings')
	@require_register
	def cmd_reset_default(self, message):
		with self.config_manager.get(self.chat_to_user[message['chat']['id']]) as (cfg, tmp):
			if 'telegram_default_timestamp' in tmp:
				del tmp['telegram_default_timestamp']
			self.reply(message, 'done.')

	def default_expired(self, tmp):
		return 'telegram_default_timestamp' not in tmp or (datetime.utcnow() - tmp['telegram_default_timestamp']) > timedelta(minutes=20)

	@help('Instantiate a template')
	@require_register
	def cmd_template(self, message):
		with self.config_manager.get(self.chat_to_user[message['chat']['id']]) as (cfg, tmp):
			if 'templates' not in cfg or not cfg['templates']['enabled']:
				return self.reply(message, 'Templates are not enabled.')
			my_templates = templates.get_templates(tmp['api'], tmp['timezone'], cfg['templates'], tmp.setdefault('templates', {}))
			template_buttons = [{
				'text': template['name'],
				'callback_data': my_json.dumps({
					'cmd': 'template',
					'template': template['id'],
				})
			} for template in my_templates]
			self.reply_keyboard(message, 'Choose template:', self.buttons_in_rows(template_buttons, 2))

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
				sync_with_retry(tmp)

				project_id = cfg['telegram'][kind + '_project']
				labels = cfg['telegram'][kind + '_labels']
				if not self.default_expired(tmp):
					project_id = tmp.get('telegram_default_project', project_id)
					labels = tmp.get('telegram_default_labels', labels)

				new_task = tmp['api'].items.add(prefix + message['text'], project_id=project_id)
				new_task.update(labels=labels[:])
				new_task.update(due={'string': 'today'})
				tmp['api'].commit()
				runner.run_now('priosorter', cfg, tmp, self.config_manager)
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
			self.change_reply(message, 'Task moved.')
		elif data['cmd'] == 'labels':
			with self.config_manager.get(userid) as (cfg, tmp):
				if 'telegram_last_task' not in tmp:
					return
				if data['label'] == -1:
					self.change_reply(message, 'Done.')
				else:
					labels = tmp['telegram_last_task']['labels'][:]
					if data['label'] in labels:
						labels.remove(data['label'])
					else:
						labels.append(data['label'])
					tmp['telegram_last_task'].update(labels=labels)
					tmp['api'].commit()
					self.change_keyboard(message, 'Choose labels:', self.create_label_buttons(tmp, 'labels', labels))
		elif data['cmd'] == 'default_project':
			with self.config_manager.get(userid) as (cfg, tmp):
				tmp['telegram_default_timestamp'] = datetime.utcnow()
				tmp['telegram_default_project'] = data['project']
			self.change_reply(message, 'Default project set.')
		elif data['cmd'] == 'default_labels':
			with self.config_manager.get(userid) as (cfg, tmp):
				tmp['telegram_default_timestamp'] = datetime.utcnow()
				if data['label'] == -1:
					self.change_reply(message, 'Default labels set.')
				else:
					if data['label'] in tmp['telegram_default_labels']:
						tmp['telegram_default_labels'].remove(data['label'])
					else:
						tmp['telegram_default_labels'].append(data['label'])
						self.change_keyboard(message, 'Choose default labels for next 20 minutes:', self.create_label_buttons(tmp, 'default_labels', tmp['telegram_default_labels']))
		elif data['cmd'] == 'template':
			with self.config_manager.get(userid) as (cfg, tmp):
				tmp['telegram_template_id'] = data['template']
				self.change_keyboard(message, 'Choose project:', self.create_project_buttons(tmp, 'template_project'))
		elif data['cmd'] == 'template_project':
			with self.config_manager.get(userid) as (cfg, tmp):
				if not tmp['telegram_template_id']:
					return self.change_reply(message, 'Something went wrong...')
				sync_if_necessary(tmp)
				templates.start(tmp['api'], tmp['timezone'], cfg['templates'], tmp.setdefault('templates', {}), tmp['telegram_template_id'], data['project'])
				self.change_reply(message, 'Template instantiated.')

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
			logger.warning('Received bad token')
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
			cfg['telegram']['chatid'] = chatid
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
