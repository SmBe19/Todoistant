from typing import cast

from config.config import Config, ConfigManager
from config.config_wrapper import ConfigWrapper


class TelegramServerConfig(ConfigWrapper):

    def __init__(self, config: Config) -> None:
        super().__init__(config)

    @staticmethod
    def get(mgr: ConfigManager) -> 'TelegramServerConfig':
        return TelegramServerConfig(mgr.get('telegram'))

    # TODO fix typing hint
    @property
    def telegram(self) -> 'telegram.telegram_server.TelegramServer':
        return cast('telegram.telegram_server.TelegramServer', self._tmp['telegram'])
