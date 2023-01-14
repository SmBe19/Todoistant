import datetime
import logging
import threading
from typing import List

from assistants.assistant import Assistant
from assistants.assistants import ASSISTANTS
from config.config import ConfigManager
from config.telegram_server_config import TelegramServerConfig
from config.user_config import UserConfig
from todoistapi.hooks import HookData
from utils.utils import sync_with_retry

logger = logging.getLogger(__name__)


def run_now(assistant: Assistant, user: UserConfig, mgr: ConfigManager) -> None:
    def send_message(message: str) -> None:
        chatid = user.cfg['telegram']['chatid']
        if chatid <= 0:
            return
        with TelegramServerConfig.get(mgr) as telegram_cfg:
            telegram_cfg.telegram.send_message(chatid, message)

    if user.acfg(assistant).enabled:
        assistant.run(user, send_message)
        user.acfg(assistant).last_run = datetime.datetime.utcnow()


class Runner:

    def __init__(self, config_manager: ConfigManager) -> None:
        self.should_shutdown: threading.Event = threading.Event()
        self.new_update: threading.Condition = threading.Condition()
        self.config_manager: ConfigManager = config_manager
        self.update_queue: List[HookData] = []

    def run_forever(self) -> None:
        try:
            self._run_forever()
        except Exception as e:
            logger.error('Error in runner', exc_info=e)

    def _run_forever(self) -> None:
        self.should_shutdown.clear()
        with self.new_update:
            while not self.should_shutdown.is_set():
                had_update = False
                while self.update_queue:
                    update = self.update_queue.pop()
                    userid = update.user_id
                    if userid not in self.config_manager:
                        continue
                    with UserConfig.get(self.config_manager, userid) as user:
                        for assistant in ASSISTANTS:
                            if user.acfg(assistant).enabled:
                                logger.debug('Check whether %s needs to handle update', assistant)
                                assistant_handle_update = assistant.handle_update(user, update)
                                logger.debug('Assistant %s needs update: %s', assistant, assistant_handle_update)
                                had_update = assistant_handle_update or had_update
                if had_update:
                    logger.debug('Received updates')

                for account in self.config_manager:
                    api_synced = False
                    with UserConfig.get(self.config_manager, account) as user:
                        if not user.enabled:
                            continue

                        for assistant in ASSISTANTS:
                            if user.acfg(assistant).enabled:
                                if assistant.should_run(user):
                                    if not api_synced:
                                        sync_with_retry(user)
                                        api_synced = True
                                    logger.debug('Run %s for %s', assistant, account)
                                    run_now(assistant, user, self.config_manager)
                                    logger.debug('Finished %s for %s', assistant, account)
                self.new_update.wait(3 if had_update else 60)

    def receive_update(self, update: HookData) -> None:
        with self.new_update:
            self.update_queue.append(update)
            self.new_update.notify_all()

    def shutdown(self) -> None:
        self.should_shutdown.set()
