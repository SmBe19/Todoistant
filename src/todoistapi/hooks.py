from typing import Dict, cast


class HookData:

    def __init__(self, data: Dict[str, object]) -> None:
        self.data: Dict[str, object] = data

    @property
    def user_id(self) -> str:
        return cast(str, self.data['user_id'])
