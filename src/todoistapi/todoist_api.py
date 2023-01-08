import datetime
from typing import Dict, Any

import todoist


class TodoistAPI:

    def __init__(self, backing_api: todoist.TodoistAPI):
        self.api: todoist.TodoistAPI = backing_api

    @property
    def state(self) -> Dict[str, Any]:
        return self.api.state

    @property
    def items(self) -> Any:
        return self.api.items

    @property
    def projects(self) -> Any:
        return self.api.projects

    @property
    def labels(self) -> Any:
        return self.api.labels

    def commit(self) -> None:
        self.api.commit()

    def sync(self) -> None:
        self.api.sync()

    @property
    def timezone(self) -> datetime.timezone:
        tz_info = self.api.state['user']['tz_info']
        timezone = datetime.timezone(
            datetime.timedelta(hours=tz_info['hours'], minutes=tz_info['minutes']),
            tz_info['timezone']
        )
        return timezone


def get_api(token) -> TodoistAPI:
    api = todoist.TodoistAPI(token, cache='./cache/')
    api.sync()
    return TodoistAPI(api)
