import base64
import logging
import os
import threading
from datetime import datetime, timedelta
from functools import wraps
from typing import Callable, Any, List, Set, Dict, cast, Collection, Union

import requests

import runner
from assistants.assistants import ASSISTANTS
from config.config import ConfigManager
from config.user_config import UserConfig
from server_handlers import sync_if_necessary
from utils import my_json
from utils.utils import sync_with_retry

logger = logging.getLogger(__name__)


def help(msg: str) -> Callable[[Callable], Callable]:
    def func(f: Callable) -> Callable:
        f.__description__ = msg
        return f

    return func


def require_register(f: Callable) -> Callable:
    @wraps(f)
    def wrapper(self, message: Any, *args, **kwargs) -> Any:
        if message['chat']['id'] not in self.chat_to_user:
            return self.reply(message, 'Sorry, you need to register to chat with me.')
        return f(self, message, *args, **kwargs)

    return wrapper


class TelegramServer:

    def __init__(self, config_manager: ConfigManager) -> None:
        self.should_shutdown: threading.Event = threading.Event()
        self.new_update: threading.Condition = threading.Condition()
        self.config_manager: ConfigManager = config_manager
        self.session: requests.Session = requests.Session()
        self.update_queue: List[Any] = []
        self.message_queue: List[(str, str)] = []
        self.processed_updates: Set[str] = set()
        self.chat_to_user: Dict[str, str] = {}
        self.pending_registrations: Dict[str, (str, str, str, datetime)] = {}

        self.token: Union[str, None] = None
        self.bot_token: str = os.environ['TELEGRAM_TOKEN']
        assert os.environ['TELEGRAM_WEBHOOK']

        self.commands: Dict[str, Callable] = {
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

    def _get_user_for_message(self, message: Any) -> UserConfig:
        return UserConfig.get(self.config_manager, self.chat_to_user[message['chat']['id']])

    def post(self, method: str, **data) -> Any:
        if not data:
            data = {}
        res = self.session.post('https://api.telegram.org/bot{}/{}'.format(self.bot_token, method), json=data).json()
        if not res['ok']:
            logger.warning('Error: %s', res['description'])
            raise RuntimeError()
        return res['result']

    def reply(self, message: Any, text: str) -> None:
        self.post('sendMessage', chat_id=message['chat']['id'], text=text)

    def reply_keyboard(self, message: Any, text: str, buttons: List[Any]) -> None:
        self.post('sendMessage', chat_id=message['chat']['id'], text=text, reply_markup={
            'inline_keyboard': buttons
        })

    def change_reply(self, message: Any, text: str):
        self.post('editMessageText', chat_id=message['chat']['id'], message_id=message['message_id'], text=text)

    def change_keyboard(self, message: Any, text: str, buttons: List[Any]):
        self.post('editMessageText', chat_id=message['chat']['id'], message_id=message['message_id'], text=text,
                  reply_markup={
                      'inline_keyboard': buttons
                  })

    def buttons_in_rows(self, buttons: List[Any], rows: int) -> List[Any]:
        inline_keyboard = []
        for i in range(0, len(buttons) + rows - 1, rows):
            inline_keyboard.append(buttons[i:i + rows])
        return inline_keyboard

    def create_project_buttons(self, user: UserConfig, cmd: str) -> List[Any]:
        sync_if_necessary(user)
        project_buttons = [
            {
                'text': project.name,
                'callback_data': my_json.dumps({
                    'cmd': cmd,
                    'project': project.id,
                }),
            } for project in user.api.projects]
        return self.buttons_in_rows(project_buttons, 2)

    def create_label_buttons(self, user: UserConfig, cmd: str, active: Collection[str]) -> List[Any]:
        sync_if_necessary(user)
        label_buttons = [
            {
                'text': '{} (on)'.format(label.name) if label.name in active else label.name,
                'callback_data': my_json.dumps({
                    'cmd': cmd,
                    'label': label.name,
                }),
            } for label in user.api.labels]
        label_buttons.append({
            'text': 'Finish.',
            'callback_data': my_json.dumps({
                'cmd': cmd,
                'label': -1,
            }),
        })
        return self.buttons_in_rows(label_buttons, 2)

    def default_expired(self, user: UserConfig) -> bool:
        return 'telegram_default_timestamp' not in user.tmp or (
                datetime.utcnow() - user.tmp['telegram_default_timestamp']) > timedelta(minutes=20)

    @help('Start the conversation with your Todoistant')
    def cmd_start(self, message: Any) -> None:
        self.reply(message,
                   'Hi {}!\n\nRegister your account by going to https://todoistant.smeanox.com and then using /register with the specified id.'.format(
                       message['chat']['first_name']))

    @help('Say hi')
    def cmd_say_hi(self, message: Any) -> None:
        self.reply(message, 'Hi {}!'.format(message['chat']['first_name']))

    @help('Shows information about the bot')
    def cmd_help(self, message: Any) -> None:
        self.reply(message, 'Currently, there is no help available. Sorry.')

    @help('Register your Todoist account')
    def cmd_register(self, message: Any) -> None:
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
        self.pending_registrations[code] = (
            userid, message['chat']['id'], message['chat']['username'], datetime.utcnow())
        self.reply(message, 'Please enter the following code to connect your account:')
        self.reply(message, code)

    @help('Change the project of the last task')
    @require_register
    def cmd_project(self, message: Any) -> None:
        with self._get_user_for_message(message) as user:
            if 'telegram_last_task' not in user.tmp:
                return self.reply(message, 'No task was added so far.')
            self.reply_keyboard(message, 'Choose project:', self.create_project_buttons(user, 'project'))

    @help('Change the default project')
    @require_register
    def cmd_default_project(self, message: Any) -> None:
        with self._get_user_for_message(message) as user:
            self.reply_keyboard(message, 'Choose default project for next 20 minutes:',
                                self.create_project_buttons(user, 'default_project'))

    @help('Change the labels of the last task')
    @require_register
    def cmd_labels(self, message: Any) -> None:
        with self._get_user_for_message(message) as user:
            if 'telegram_last_task' not in user.tmp:
                return self.reply(message, 'No task was added so far.')
            self.reply_keyboard(message, 'Choose labels:',
                                self.create_label_buttons(user, 'labels', user.tmp['telegram_last_task'].labels))

    @help('Change the default labels')
    @require_register
    def cmd_default_labels(self, message: Any) -> None:
        with self._get_user_for_message(message) as user:
            if 'telegram_default_labels' not in user.tmp or self.default_expired(user):
                user.tmp['telegram_default_labels'] = []
            self.reply_keyboard(message, 'Choose default labels for next 20 minutes:',
                                self.create_label_buttons(user, 'default_labels',
                                                          cast(List[str], user.tmp['telegram_default_labels'])))

    @help('Reset the default settings')
    @require_register
    def cmd_reset_default(self, message: Any) -> None:
        with self._get_user_for_message(message) as user:
            if 'telegram_default_timestamp' in user.tmp:
                del user.tmp['telegram_default_timestamp']
            self.reply(message, 'done.')

    @help('Instantiate a template')
    @require_register
    def cmd_template(self, message: Any) -> None:
        with self._get_user_for_message(message) as user:
            if not user.acfg(ASSISTANTS.templates).enabled:
                return self.reply(message, 'Templates are not enabled.')
            my_templates = ASSISTANTS.templates.get_templates(user)
            template_buttons = [{
                'text': template.name,
                'callback_data': my_json.dumps({
                    'cmd': 'template',
                    'template': template.id,
                })
            } for template in my_templates]
            self.reply_keyboard(message, 'Choose template:', self.buttons_in_rows(template_buttons, 2))

    def handle_normal_message(self, message: Any) -> None:
        chatid = message['chat']['id']
        userid = self.chat_to_user[chatid]
        link = None
        if 'entities' in message:
            for entity in message['entities']:
                if entity['type'] == 'url':
                    link = message['text'][entity['offset']:entity['offset'] + entity['length']]
                    break

        def handle_message(kind: str, prefix: str = '') -> None:
            with UserConfig.get(self.config_manager, userid) as user:
                cfg = user.acfg(ASSISTANTS.telegram)
                if not cfg.enabled:
                    self.reply(message, 'Telegram is disabled for your account. Please enable it to chat with me.')
                    return
                if kind + '_project' not in cfg:
                    self.reply(message, 'Sorry, I don\'t know how to handle this type of message.')
                    return
                sync_with_retry(user)

                project_id = cfg[kind + '_project']
                labels = cfg[kind + '_labels']
                if not self.default_expired(user):
                    project_id = user.tmp.get('telegram_default_project', project_id)
                    labels = user.tmp.get('telegram_default_labels', labels)

                new_task = user.api.items.add(
                    prefix + message['text'],
                    project_id=project_id,
                    labels=labels[:],
                    due={'string': 'today'})
                user.api.commit()
                runner.run_now(ASSISTANTS.priosorter, user, self.config_manager)
                user.tmp['telegram_last_task'] = new_task
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

    def process(self, message: Any) -> None:
        if message['chat']['type'] != 'private':
            return self.reply(message, 'This bot is only available in private chats.')
        command = None
        if 'entities' in message:
            for entity in message['entities']:
                if entity['type'] == 'bot_command':
                    command = message['text'][entity['offset']:entity['offset'] + entity['length']].split('@')[0]
                    break
            if command == '/start':
                return self.cmd_start(message)
            if command in self.commands:
                return self.commands[command](message)
        if message['chat']['id'] not in self.chat_to_user:
            return self.reply(message, 'Sorry, you need to register to chat with me.')
        self.handle_normal_message(message)

    def process_inline(self, query: Any) -> None:
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
            with UserConfig.get(self.config_manager, userid) as user:
                if 'telegram_last_task' not in user.tmp:
                    return
                user.tmp['telegram_last_task'].move(project_id=data['project'])
                user.api.commit()
            self.change_reply(message, 'Task moved.')
        elif data['cmd'] == 'labels':
            with UserConfig.get(self.config_manager, userid) as user:
                if 'telegram_last_task' not in user.tmp:
                    return
                if data['label'] == -1:
                    self.change_reply(message, 'Done.')
                else:
                    labels = user.tmp['telegram_last_task'].labels[:]
                    if data['label'] in labels:
                        labels.remove(data['label'])
                    else:
                        labels.append(data['label'])
                    user.tmp['telegram_last_task'].labels = labels
                    user.api.commit()
                    self.change_keyboard(message, 'Choose labels:', self.create_label_buttons(user, 'labels', labels))
        elif data['cmd'] == 'default_project':
            with UserConfig.get(self.config_manager, userid) as user:
                user.tmp['telegram_default_timestamp'] = datetime.utcnow()
                user.tmp['telegram_default_project'] = data['project']
            self.change_reply(message, 'Default project set.')
        elif data['cmd'] == 'default_labels':
            with UserConfig.get(self.config_manager, userid) as user:
                user.tmp['telegram_default_timestamp'] = datetime.utcnow()
                if data['label'] == -1:
                    self.change_reply(message, 'Default labels set.')
                else:
                    if data['label'] in user.tmp['telegram_default_labels']:
                        user.tmp['telegram_default_labels'].remove(data['label'])
                    else:
                        user.tmp['telegram_default_labels'].append(data['label'])
                    self.change_keyboard(message, 'Choose default labels for next 20 minutes:',
                                         self.create_label_buttons(user, 'default_labels',
                                                                   user.tmp['telegram_default_labels']))
        elif data['cmd'] == 'template':
            with UserConfig.get(self.config_manager, userid) as user:
                user.tmp['telegram_template_id'] = data['template']
                self.change_keyboard(message, 'Choose project:', self.create_project_buttons(user, 'template_project'))
        elif data['cmd'] == 'template_project':
            with UserConfig.get(self.config_manager, userid) as user:
                if not user.tmp['telegram_template_id']:
                    return self.change_reply(message, 'Something went wrong...')
                sync_if_necessary(user)
                self.change_reply(message, 'Template instantiating...')
                ASSISTANTS.templates.start(user, user.tmp['telegram_template_id'], data['project'])
                self.change_reply(message, 'Template instantiated.')

    def run_forever(self) -> None:
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

    def receive(self, token: str, update: Any):
        if token != self.token:
            logger.warning('Received bad token')
            return
        with self.new_update:
            self.update_queue.append(update)
            self.new_update.notify_all()

    def send_message(self, receiver: str, text: str) -> None:
        if not receiver:
            return
        with self.new_update:
            self.message_queue.append((receiver, text))
            self.new_update.notify_all()

    def finish_register(self, account: str, code: str) -> str:
        if code not in self.pending_registrations:
            return 'invalid code'
        userid, chatid, username, timestamp = self.pending_registrations[code]
        del self.pending_registrations[code]
        if str(userid) != str(account):
            return 'invalid account'
        if (datetime.utcnow() - timestamp) > timedelta(minutes=15):
            return 'expired code'
        with UserConfig.get(self.config_manager, userid) as user:
            cfg = user.acfg(ASSISTANTS.telegram)
            cfg['chatid'] = chatid
            cfg['username'] = username
        self.chat_to_user[chatid] = userid
        with self.new_update:
            self.message_queue.append((chatid, 'Successfully connected account!'))
            self.new_update.notify_all()
        return 'ok'

    def shutdown(self) -> None:
        self.should_shutdown.set()
        with self.new_update:
            self.new_update.notify_all()
