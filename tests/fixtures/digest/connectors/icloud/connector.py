"""A calendar that does what the plan says."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from _plan import plan, refuse  # noqa: E402

from harry.sdk import Context, Registry  # noqa: E402

WORKING = [{'at': '09:30', 'ends': '10:00', 'title': 'standup', 'where': 'room', 'calendar': 'Shaun'}]


class Agenda:
    def __init__(self) -> None:
        self.asked = 0

    def today(self) -> list[dict]:
        how = plan('icloud')
        self.asked += 1
        refuse(how)
        return how.get('events', WORKING)


def register(registry: Registry, context: Context) -> None:
    registry.connector(Agenda())
