"""A news source that does what the plan says."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from _plan import plan, refuse  # noqa: E402

from harry.sdk import Context, Registry  # noqa: E402


class News:
    def __init__(self) -> None:
        self.asked: list[dict] = []

    def search(self, **how) -> dict:
        wanted = plan('news')
        self.asked.append(how)
        refuse(wanted)
        many = wanted.get('many', 3)
        made = [
            {'id': f'vrt-2026-09-15-story-{n}', 'title': f'Story {n}', 'source': 'VRT NWS',
             'feed': 'vrt', 'date': '2026-09-15', 'summary': 'A summary.' * (40 if wanted.get('long') else 1),
             'image': None}
            for n in range(many)
        ]
        return {'candidates': made[: how.get('limit', 20)], 'unavailable': wanted.get('unavailable', [])}


def register(registry: Registry, context: Context) -> None:
    registry.connector(News())
