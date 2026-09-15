"""What every capability test needs, and one thing it must never take with it.

A capability test copies the real folder out of `.harry/` into a temporary root and loads it
from there — declaration, generated `.env`, Python and all. That is the point: the
declaration, the config resolution and the registration are then under test together, rather
than a hand-built approximation of them.

**What must not come along is anything the working tree happens to be holding.** A capability
folder can carry a gitignored `.env.local`, and `harry.config` reads it ahead of the committed
`.env` — by design, because that is how a machine says what differs about it. Copied into a
test, it makes the suite answer differently on every laptop.

Measured on the machine where this was found, whose `.harry/connectors/news/.env.local` names
a third feed: **fifty-six tests fail** — thirty-seven of the fifty-one in
`test_news_connector.py`, nineteen of the twenty-four in `test_news_tools.py`. Every one of
them fails on `respx` refusing a request no fixture mocks, so nothing actually leaves the
machine; what breaks is the suite's answer, not the network rule. On a laptop with no such
file all fifty-six pass and nothing says why.

So one helper does the copying, and `test_capability_copy.py` fails if a test file reaches
for `shutil.copytree` on `.harry/` some other way.
"""

from __future__ import annotations

import shutil
from pathlib import Path

LEAVE_BEHIND = ('.env.local', '__pycache__', '*.pyc')
"""What the working tree holds and a test must not inherit.

`.env.local` is the one that bites: it is read ahead of the committed `.env`, so it changes
what the capability under test is configured to do. The other two are the same class of leak —
a stale `.pyc` compiled against code that has since changed, whether it sits in `__pycache__`
or loose beside the source, which is where one lands if somebody ran the file directly.
"""


def copy_capability(source: Path, destination: Path) -> Path:
    """One capability folder into a temporary root, without this machine's settings.

    Returns the destination, so a caller can keep chaining.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination, dirs_exist_ok=True, ignore=shutil.ignore_patterns(*LEAVE_BEHIND))
    return destination
