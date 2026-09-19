"""A forecast that does what the plan says."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from _plan import plan, refuse  # noqa: E402

from harry.sdk import Context, Registry  # noqa: E402

WORKING = {
    'available': True,
    'place': 'Leuven',
    'summary': 'overcast',
    'high': 29,
    'low': 17,
    'rain_chance': 53,
    'sunrise': '07:22',
    'sunset': '19:46',
    'hours': [{'at': '06:00', 'temperature': 17, 'summary': 'clear'}],
}


class Forecast:
    def __init__(self) -> None:
        self.asked = 0

    def forecast(self) -> dict:
        how = plan('weather')
        self.asked += 1
        refuse(how)
        # `if 'answer' in how`, not `or` — a plan that asks for
        # `{'available': False, 'why': …}` must arrive verbatim, and the falsy-or made that
        # shape unexpressible, which is how the bug this fixture now covers went unseen.
        return how['answer'] if 'answer' in how else WORKING


def register(registry: Registry, context: Context) -> None:
    registry.connector(Forecast())
