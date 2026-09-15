"""Call one of Harry's tools from the command line, with no server and no client.

    uv run python scripts/call_tool.py digest_list_candidates
    uv run python scripts/call_tool.py digest_build --args '{"intro": "…", "picks": [...]}'
    uv run python scripts/call_tool.py digest_build --args @picks.json

**Generic on purpose.** `make digest-dry` names a tool in a Makefile recipe, which is a
developer convenience — and nothing in `src/harry/` learns a capability's name. A script that
knew about the digest would be the first place core started to.

It loads the capabilities the way the server does, so a tool that is skipped here is a tool
that would be skipped there, and it says which and why rather than failing on a `KeyError`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from harry.loader import load  # noqa: E402
from harry.main import configure_logging  # noqa: E402


def arguments(given: str | None) -> dict[str, Any]:
    """The tool's arguments, as JSON or as `@a-file.json`.

    A file because `digest_build` takes an intro, six picks and a dozen more, and that does
    not belong on a command line.
    """
    if not given:
        return {}
    if given.startswith('@'):
        given = Path(given[1:]).read_text(encoding='utf-8')
    found = json.loads(given)
    if not isinstance(found, dict):
        raise SystemExit("--args must be a JSON object of the tool's named arguments")
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('tool', help='the tool to call, by name')
    parser.add_argument('--args', help='its arguments as JSON, or @file.json')
    parser.add_argument('--quiet', action='store_true', help='print the answer and nothing else')
    chosen = parser.parse_args(argv)

    configure_logging()
    catalogue = load()
    found = catalogue.get('tool', chosen.tool)
    if found is None:
        known = sorted(c.name for c in catalogue.loaded if c.kind == 'tool')
        raise SystemExit(f'no tool called {chosen.tool!r}. There is: {", ".join(known) or "none"}')
    if found.target is None:
        raise SystemExit(f'{chosen.tool} did not load: {found.reason}')

    answer = found.target(**arguments(chosen.args))
    print(json.dumps(answer, indent=1, default=str))
    if not chosen.quiet:
        missing = [f'{c.name}: {c.reason}' for c in catalogue.skipped]
        if missing:
            print('\nnot loaded, so not on the page:', file=sys.stderr)
            for one in missing:
                print(f'  {one}', file=sys.stderr)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
