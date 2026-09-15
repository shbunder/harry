"""A news source that does what the plan says."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from _plan import plan, refuse  # noqa: E402

from harry.sdk import Context, Registry  # noqa: E402


class News:
    def __init__(self) -> None:
        self.asked: list[dict] = []
        self.read: list[str] = []

    def article(self, story_id: str) -> dict:
        """One story's text, or why there is none."""
        wanted = plan('news')
        self.read.append(story_id)
        if story_id in (wanted.get('unreadable') or []):
            return {
                'available': False, 'id': story_id, 'title': f'Story {story_id[-1]}',
                'source': 'VRT NWS', 'published': '2026-09-15T06:00:00+00:00',
                'link': f'https://example.test/{story_id}', 'summary': 'A summary.',
                'image': None, 'why': 'it answered 403',
            }
        return {
            'available': True, 'id': story_id, 'title': f'Story {story_id[-1]}',
            'source': 'VRT NWS', 'published': '2026-09-15T06:00:00+00:00',
            'link': f'https://example.test/{story_id}', 'summary': 'A summary.',
            'image': wanted.get('image'),
            'text': 'One paragraph.\n\nAnd a second one, long enough to set in two columns.',
        }

    def search(self, **how) -> dict:
        wanted = plan('news')
        self.asked.append(how)
        refuse(wanted)
        many = wanted.get('many', 3)
        made = [
            {'id': f'vrt-2026-09-15-story-{n}-and-what-came-of-it', 'title': f'Story {n}', 'source': 'VRT NWS',
             'feed': 'vrt', 'date': '2026-09-15', 'summary': 'A summary.' * (40 if wanted.get('long') else 1),
             'image': wanted.get('image')}
            for n in range(many)
        ]
        return {'candidates': made[: how.get('limit', 20)], 'unavailable': wanted.get('unavailable', [])}


def register(registry: Registry, context: Context) -> None:
    registry.connector(News())
