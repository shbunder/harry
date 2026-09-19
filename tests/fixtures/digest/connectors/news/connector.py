"""A news source that does what the plan says."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from _plan import plan, refuse  # noqa: E402

from harry.sdk import Context, Registry  # noqa: E402


LONG = 'Vlaams minister stuurt West-Vlaams gouverneur naar de kust voor verkennend onderzoek'
"""A real headline runs to a dozen words and wraps to three lines, which is most of a story's
height on the second sheet. `Story 5` wraps to none, so a sheet built from those holds about
twice what a morning's actually does."""


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
                'available': False,
                'id': story_id,
                'title': f'Story {story_id[-1]}',
                'source': 'VRT NWS',
                'published': '2026-09-15T06:00:00+00:00',
                'link': f'https://example.test/{story_id}',
                'summary': 'A summary.',
                'image': None,
                'why': 'it answered 403',
            }
        return {
            'available': True,
            'id': story_id,
            # The page prints the article's title, not the candidate's, so a long headline has
            # to be here to reach the page at all.
            'title': f'{LONG} {story_id[-1]}' if wanted.get('real_titles') else f'Story {story_id[-1]}',
            'source': 'VRT NWS',
            'published': '2026-09-15T06:00:00+00:00',
            'link': f'https://example.test/{story_id}',
            # `summary` is a feed's own, markup and all — KW's arrives as HTML.
            'summary': wanted.get('summary') or 'A summary.',
            # `page_image` is what the article's own page shows when the feed published none —
            # the real connector answers with the feed's picture or the page's, in that order.
            'image': wanted.get('image') or wanted.get('page_image'),
            'text': 'One paragraph.\n\nAnd a second one, long enough to set in two columns.',
        }

    def search(self, **how) -> dict:
        wanted = plan('news')
        self.asked.append(how)
        refuse(wanted)
        many = wanted.get('many', 3)
        if wanted.get('collide'):
            # What `News._unique` really produces when two same-day stories share their first
            # five title words: the second id is the first with `-2` on the end.
            made = [
                {
                    'id': 'vrt-2026-09-15-story-0-and-what-came-of-it',
                    'title': 'Story 0',
                    'source': 'VRT NWS',
                    'feed': 'vrt',
                    'date': '2026-09-15',
                    'summary': 'A summary.',
                    'image': wanted.get('image'),
                },
                {
                    'id': 'vrt-2026-09-15-story-0-and-what-came-of-it-2',
                    'title': 'Story 0b',
                    'source': 'VRT NWS',
                    'feed': 'vrt',
                    'date': '2026-09-15',
                    'summary': 'A summary.',
                    'image': wanted.get('image'),
                },
            ]
            return {'candidates': made, 'unavailable': []}
        headline = LONG if wanted.get('real_titles') else 'Story'
        made = [
            {
                'id': f'vrt-2026-09-15-story-{n}-and-what-came-of-it',
                'title': f'{headline} {n}',
                'source': 'VRT NWS',
                'feed': 'vrt',
                'date': '2026-09-15',
                'summary': wanted.get('summary') or 'A summary.' * (40 if wanted.get('long') else 1),
                'image': wanted.get('image'),
            }
            for n in range(many)
        ]
        # A local paper, newest of all, so a tool that does not hold it back puts it first.
        # Half of them name the place and half do not, which is the whole point of the filter.
        for n in range(wanted.get('local', 0)):
            names = n % 2 == 0
            made.insert(
                n,
                {
                    'id': f'kw-2026-09-15-local-{n}-and-what-came-of-it',
                    'title': f'Something in Oostende {n}' if names else f'Something in De Panne {n}',
                    'source': 'KW West-Vlaanderen',
                    'feed': 'kw',
                    'date': '2026-09-15',
                    'summary': 'A summary.',
                    'image': wanted.get('image'),
                },
            )
        return {'candidates': made[: how.get('limit', 20)], 'unavailable': wanted.get('unavailable', [])}


def register(registry: Registry, context: Context) -> None:
    registry.connector(News())
