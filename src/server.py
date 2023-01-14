import argparse
import datetime
import logging
import os
import socketserver
import threading
import time
from logging.handlers import RotatingFileHandler

import dotenv

import runner
import server_handlers
from assistants.assistants import ASSISTANTS
from config.config import ConfigManager
from config.user_config import UserConfig
from telegram.telegram_server import TelegramServer
from todoistapi import todoist_api
from utils import my_json
from utils.consts import SOCKET_NAME, CACHE_PATH, CONFIG_PATH

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

    def handle(self) -> None:
        for line in self.rfile:
            if not line:
                continue
            try:
                data = my_json.loads(line.strip())
            except ValueError as e:
                logger.warning('Invalid Request', e)
                continue
            if data['cmd'] in server_handlers.handlers:
                res = server_handlers.handlers[data['cmd']](*data.get('args', []), **data.get('kwargs', {}),
                                                            mgr=config_manager)
                self.wfile.write((my_json.dumps(res) + '\n').encode())


class ThreadingServer(socketserver.UnixStreamServer, socketserver.ThreadingMixIn):
    pass


def init_fs() -> None:
    if os.path.exists(SOCKET_NAME):
        os.remove(SOCKET_NAME)
    if not os.path.isdir(CACHE_PATH):
        os.mkdir(CACHE_PATH)
    if not os.path.exists(CONFIG_PATH):
        os.mkdir(CONFIG_PATH)


def init_config() -> None:
    logger.info('Load config...')
    for file in os.listdir(CONFIG_PATH):
        if file.endswith('.json'):
            userid = file[:-5]
            logger.info('Load config for user %s...', userid)
            account = config_manager.get(userid)
            account.load()
            with account as (cfg, tmp):
                if cfg['enabled']:
                    tmp['api'] = todoist_api.get_api(cfg['token'])
                    tmp['api_last_sync'] = datetime.datetime.utcnow()
            with UserConfig.get(config_manager, userid) as user:
                for assistant in ASSISTANTS:
                    acfg = user.acfg(assistant)
                    if not acfg.enabled:
                        continue
                    old_version = acfg['config_version']
                    if old_version < assistant.get_config_version():
                        logger.info('Migrate %s from config version %s to %s', assistant,
                                    old_version, assistant.get_config_version())
                        assistant.migrate_config(user, acfg, old_version)
                        acfg['config_version'] = assistant.get_config_version()
            logger.info('Config loaded for user %s...', userid)
    logger.info('Config loaded')


def start_server() -> ThreadingServer:
    logger.info('Starting server...')
    server = ThreadingServer(SOCKET_NAME, RequestHandler)
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()
    logger.info('Server started')
    return server


def start_telegram() -> TelegramServer:
    logger.info('Starting telegram...')
    my_telegram = TelegramServer(config_manager)
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
    return my_telegram


def start_runner() -> runner.Runner:
    logger.info('Starting runner...')
    my_runner = runner.Runner(config_manager)
    runner_thread = threading.Thread(target=my_runner.run_forever)
    runner_thread.daemon = True
    runner_thread.start()
    config_manager.dummy_configs.add('runner')
    with config_manager.get('runner') as (cfg, tmp):
        tmp['runner'] = my_runner
    logger.info('Runner started')
    return my_runner


def run_server(args: argparse.Namespace) -> None:
    init_fs()
    init_config()
    server = start_server()
    my_telegram = start_telegram()
    my_runner = start_runner()

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
