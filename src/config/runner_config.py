from typing import Set, cast

import runner
from config.config import Config, ConfigManager
from config.config_wrapper import ConfigWrapper


class RunnerConfig(ConfigWrapper):

    def __init__(self, config: Config) -> None:
        super().__init__(config)

    @staticmethod
    def get(mgr: ConfigManager) -> 'RunnerConfig':
        return RunnerConfig(mgr.get('runner'))

    @property
    def processed_hooks(self) -> Set[str]:
        return cast(Set[str], self._tmp.setdefault('processed_hooks', set()))

    @property
    def runner(self) -> 'runner.Runner':
        return cast('runner.Runner', self._tmp['runner'])
