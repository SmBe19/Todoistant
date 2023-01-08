from typing import Dict, Iterator, List, Iterable

from assistants.assistant import Assistant
from assistants.automover import AutoMover
from assistants.priosorter import PrioSorter
from assistants.telegram import Telegram
from assistants.templates import Templates


class Assistants:

    def __init__(self) -> None:
        self.priosorter: PrioSorter = PrioSorter()
        self.automover: AutoMover = AutoMover()
        self.telegram: Telegram = Telegram()
        self.templates: Templates = Templates()
        self.mapping: Dict[str, Assistant] = {
            x.get_id(): x
            for x in self.get_all()
        }

    def __iter__(self) -> Iterator[Assistant]:
        return iter(self.get_all())

    def __getitem__(self, item: str) -> Assistant:
        return self.mapping[item]

    def __contains__(self, item: str) -> bool:
        return item in self.mapping

    def get_all(self) -> List[Assistant]:
        return [
            self.priosorter,
            self.automover,
            self.telegram,
            self.templates,
        ]

    def keys(self) -> Iterable[str]:
        return map(lambda x: x.get_id(), self.get_all())


ASSISTANTS = Assistants()
