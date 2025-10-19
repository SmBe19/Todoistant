import datetime
from typing import Callable, Dict, List, Any, Union

from assistants.assistants import ASSISTANTS
from config.config import ConfigManager, ChangeDict
from config.runner_config import RunnerConfig
from config.telegram_server_config import TelegramServerConfig
from config.user_config import UserConfig
from todoistapi import todoist_api
from todoistapi.hooks import HookData
from utils.utils import sync_if_necessary, sort_projects

handlers = {}


def handler(f: Callable) -> Callable:
    handlers[f.__name__] = f
    return f


@handler
def add_account(account: str, mgr: ConfigManager) -> str:
    if account not in mgr:
        with UserConfig.get(mgr, account) as user:
            user.cfg['enabled'] = False
    return 'ok'


@handler
def account_exists(account: str, mgr: ConfigManager) -> bool:
    return account in mgr


@handler
def enable_account(account: str, enabled: bool, mgr: ConfigManager) -> str:
    if account not in mgr:
        return 'unknown account'
    with UserConfig.get(mgr, account) as user:
        if enabled and not user.token:
            return 'can only enable if token is set'
        user.cfg['enabled'] = enabled
    return 'ok'


@handler
def set_token(account: str, token: str, mgr: ConfigManager) -> str:
    if account not in mgr:
        return 'unknown account'
    api = todoist_api.get_api(token)
    if not api.had_successful_sync():
        return 'bad token'
    with UserConfig.get(mgr, account) as user:
        user.cfg['enabled'] = True
        user.cfg['token'] = token
        user.tmp['api'] = api
        user.api_last_sync = datetime.datetime.utcnow()
    return 'ok'


@handler
def set_enabled(account: str, assistant: str, enabled: bool, mgr: ConfigManager) -> str:
    if assistant not in ASSISTANTS:
        return 'unknown assistant'
    if account not in mgr:
        return 'unknown account'
    with UserConfig.get(mgr, account) as user:
        if assistant not in user.cfg:
            user.cfg[assistant] = ASSISTANTS[assistant].get_init_config()
            user.cfg[assistant]['config_version'] = ASSISTANTS[assistant].get_config_version()
        user.cfg[assistant]['enabled'] = enabled
    return 'ok'


@handler
def get_config(account: str, mgr: ConfigManager) -> Union[Dict[str, object], None]:
    if account not in mgr:
        return None
    with UserConfig.get(mgr, account) as user:
        cfg_dict = user.cfg.to_dict()
        del cfg_dict['token']
        return cfg_dict


@handler
def update_config(account: str, update: Dict[str, Any], mgr: ConfigManager) -> str:
    if account not in mgr:
        return 'unknown account'

    def do_update(cfg: ChangeDict, upd: Dict[str, Any]):
        for key in upd:
            if key not in cfg:
                cfg[key] = upd[key]
            elif isinstance(upd[key], dict):
                do_update(cfg[key], upd[key])
            else:
                cfg[key] = upd[key]

    with UserConfig.get(mgr, account) as user:
        do_update(user.cfg, update)

    return 'ok'


@handler
def get_projects(account: str, mgr: ConfigManager) -> Union[List[object], None]:
    if account not in mgr:
        return None
    with UserConfig.get(mgr, account) as user:
        sync_if_necessary(user)
        return [{
            'name': project.name,
            'id': project.id,
        } for project in sort_projects(user.api.projects)]


@handler
def get_labels(account: str, mgr: ConfigManager) -> Union[List[object], None]:
    if account not in mgr:
        return None
    with UserConfig.get(mgr, account) as user:
        sync_if_necessary(user)
        return [{
            'name': label.name,
            'id': label.id,
        } for label in user.api.labels]


@handler
def get_templates(account: str, mgr: ConfigManager) -> Union[List[object], None]:
    if account not in mgr:
        return None
    with UserConfig.get(mgr, account) as user:
        sync_if_necessary(user)
        if 'templates' not in user.cfg:
            return []
        return ASSISTANTS.templates.get_templates(user)


@handler
def start_template(account: str, template: str, project: str, mgr: ConfigManager) -> Union[str, None]:
    if account not in mgr:
        return None
    with UserConfig.get(mgr, account) as user:
        sync_if_necessary(user)
        ASSISTANTS.templates.start(user, template, project)
    return 'ok'


@handler
def telegram_update(token: str, update: Any, mgr: ConfigManager) -> str:
    with TelegramServerConfig.get(mgr) as telegram_cfg:
        telegram_cfg.telegram.receive(token, update)
    return 'ok'


@handler
def telegram_disconnect(account: str, mgr: ConfigManager) -> str:
    if account not in mgr:
        return 'unknown account'

    with UserConfig.get(mgr, account) as user:
        chatid = user.cfg['telegram']['chatid']
        with TelegramServerConfig.get(mgr) as telegram_cfg:
            telegram_cfg.telegram.send_message(chatid, 'Account was disconnected.')
            del telegram_cfg.telegram.chat_to_user[chatid]
        user.cfg['telegram']['chatid'] = 0
        user.cfg['telegram']['username'] = ''
    return 'ok'


@handler
def telegram_connect(account: str, code: str, mgr: ConfigManager) -> str:
    with TelegramServerConfig.get(mgr) as telegram_cfg:
        return telegram_cfg.telegram.finish_register(account, code)


@handler
def todoist_hook(hook_id: str, hook_data: Dict[str, object], mgr: ConfigManager) -> str:
    with RunnerConfig.get(mgr) as runner_cfg:
        if hook_id in runner_cfg.processed_hooks:
            return 'ok'
        runner_cfg.processed_hooks.add(hook_id)
        runner_cfg.runner.receive_update(HookData(hook_data))
        return 'ok'
