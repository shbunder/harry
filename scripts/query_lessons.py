#!/usr/bin/env python3
"""Search what past features taught us.

Every closed feature carries a `## Lessons Learned` section. This mines them, ranks by
how many of your keywords appear, and prints the most relevant most recently.

`/new-feature` runs this as step 1, before a single requirement is written — because the
expensive mistake is rarely a new one.

    python scripts/query_lessons.py remarkable push retry
    python scripts/query_lessons.py playwright storage state --top 3
    python scripts/query_lessons.py feed parsing --since 260101
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path

SUMMARY = (__doc__ or '').partition('\n')[0]

BOARD = Path(__file__).parent.parent / 'project'
SECTION_RE = re.compile(r'^## Lessons Learned\s*\n(.*?)(?=\n## |\Z)', re.MULTILINE | re.DOTALL)
ID_DATE_RE = re.compile(r'-(\d{6})-')


@dataclass
class Lesson:
    item_id: str
    title: str
    date: str
    body: str
    score: int

    def render(self) -> str:
        head = f'━━ {self.item_id} — {self.title}  ({self.date}, {self.score} hit{"s" if self.score != 1 else ""})'
        return f'{head}\n{self.body.strip()}\n'


def extract(path: Path, keywords: list[str]) -> Lesson | None:
    """Pull one item's lessons and score them against the keywords.

    The title counts toward the score as well as the body: a feature literally called
    "the morning page" is exactly what someone searching `morning` is looking for, even if its
    lessons happen to phrase things differently.

    Returns `None` when the item has no lessons section, or when nothing matched.
    """
    text = path.read_text(encoding='utf-8')
    match = SECTION_RE.search(text)
    if not match:
        return None

    body = match.group(1)
    title_match = re.search(r'^title:\s*(.+)$', text, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else path.stem

    haystack = f'{title}\n{body}'.lower()
    score = sum(haystack.count(keyword.lower()) for keyword in keywords) if keywords else 1
    if score == 0:
        return None

    date_match = ID_DATE_RE.search(path.name)
    return Lesson(
        item_id='-'.join(path.stem.split('-')[:3]),
        title=title,
        date=date_match.group(1) if date_match else '??????',
        body=body,
        score=score,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='query_lessons.py', description=SUMMARY)
    parser.add_argument('keywords', nargs='*', help='terms to rank by; omit to list everything')
    parser.add_argument('--top', type=int, default=5, help='how many to show (default 5)')
    parser.add_argument('--since', help='only items whose id date is on or after YYMMDD')
    args = parser.parse_args(argv)

    lessons: list[Lesson] = []
    for path in sorted(BOARD.glob('features/FEAT-*.md')) + sorted(BOARD.glob('stories/STORY-*.md')):
        lesson = extract(path, args.keywords)
        if lesson and (not args.since or lesson.date >= args.since):
            lessons.append(lesson)

    if not lessons:
        # Not an error — an empty board is the normal state early on, and treating it
        # as a failure would teach people to skip the step.
        print('No lessons recorded yet' if not args.keywords else 'No lessons match those terms.')
        return 0

    # Best match first, then most recent — a strong old lesson still beats a weak new one.
    lessons.sort(key=lambda lesson: (-lesson.score, lesson.date), reverse=False)
    for lesson in lessons[: args.top]:
        print(lesson.render())

    if len(lessons) > args.top:
        print(f'… and {len(lessons) - args.top} more. Raise --top to see them.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
