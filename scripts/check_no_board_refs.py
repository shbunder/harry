#!/usr/bin/env python3
"""Fail if a board id appears in source code.

Code is the record of *what*. `project/` is the record of *why*. A `FEAT-…` in a
comment is a pointer into a file the reader has to go and open, it goes stale the
moment the feature is renamed, and it is never the reason the line exists — the reason
belongs in the sentence itself.

Only an id that **resolves to a real board item** counts. An id-shaped string that
matches nothing on the board is not a reference to anything — it is test data, and a
guard that cannot tell the two apart makes the board's own tests unwritable.

Run by `make lint`. See `.claude/rules/code-has-no-board-refs.md`.

    python scripts/check_no_board_refs.py           # the whole tree
    python scripts/check_no_board_refs.py --diff    # only what this branch changed
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

SUMMARY = (__doc__ or '').partition('\n')[0]

ROOT = Path(__file__).parent.parent
BOARD_ID_RE = re.compile(r'\b(?:FEAT|STORY|ADR)-\d{6}-[0-9a-f]{6}\b')

# The board writes about itself, the rules quote the format, and this file carries the
# pattern. Everything else is code.
EXEMPT_PREFIXES = ('project/', 'docs/', '.claude/', 'scripts/check_no_board_refs.py', 'README.md', 'CLAUDE.md')
SOURCE_SUFFIXES = ('.py', '.pyi', '.toml', '.yaml', '.yml', '.css', '.html', '.sh', '.sql')


def board_ids() -> set[str]:
    """Every id the board actually carries, read from the filenames that hold them.

    The filename is the right source rather than the frontmatter: it is what `board.py`
    globs on, so an id that is findable there is exactly an id a comment could point at.
    """
    board = ROOT / 'project'
    found: set[str] = set()
    for directory in ('features', 'stories', 'decisions'):
        for path in board.glob(f'{directory}/*.md'):
            match = BOARD_ID_RE.match(path.name)
            if match:
                found.add(match.group())
    return found


def candidates(diff_only: bool) -> list[Path]:
    """Tracked source files, optionally narrowed to what this branch changed."""
    if diff_only:
        base = subprocess.run(
            ['git', '-C', str(ROOT), 'merge-base', 'HEAD', 'main'],
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()
        args = ['diff', '--name-only', f'{base}...HEAD'] if base else ['ls-files']
    else:
        args = ['ls-files']

    listed = subprocess.run(
        ['git', '-C', str(ROOT), *args], capture_output=True, text=True, check=False
    ).stdout.splitlines()

    return [
        ROOT / name
        for name in listed
        if name.endswith(SOURCE_SUFFIXES) and not name.startswith(EXEMPT_PREFIXES) and (ROOT / name).is_file()
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='check_no_board_refs.py', description=SUMMARY)
    parser.add_argument('--diff', action='store_true', help='only files this branch changed')
    args = parser.parse_args(argv)

    real = board_ids()
    if not real:
        print('✓ no board ids in source (the board is empty, so nothing could be cited)')
        return 0

    hits: list[str] = []
    for path in candidates(args.diff):
        try:
            lines = path.read_text(encoding='utf-8').splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        for number, line in enumerate(lines, start=1):
            for match in BOARD_ID_RE.finditer(line):
                if match.group() in real:
                    hits.append(f'{path.relative_to(ROOT)}:{number}: {match.group()}  |  {line.strip()[:90]}')

    if not hits:
        print('✓ no board ids in source')
        return 0

    print(f'{len(hits)} reference(s) to a real board item, in source code:\n', file=sys.stderr)
    for hit in hits:
        print(f'  {hit}', file=sys.stderr)
    print(
        '\nSay the reason in the comment instead of pointing at the item that carries it.\n'
        'See .claude/rules/code-has-no-board-refs.md.',
        file=sys.stderr,
    )
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
