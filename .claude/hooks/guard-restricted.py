#!/usr/bin/env python3
"""PreToolUse guard: block casual edits to paths that decide who can do what.

Exit 0 allows the edit. Exit 2 blocks it and shows stderr to the agent.

The point is not that these files are sacred — it is that changing them should be a
deliberate act with a decision behind it, not a side effect of some other task. An agent
that can silently widen its own permissions, rewrite its own instructions, or reach a
credential that grants total access to a tablet is not **Bounded**.

Escape hatch, when the change *is* the task::

    touch .claude/.unlock-safety
    # ... make the edit, commit it ...
    rm .claude/.unlock-safety

This fails **open** on malformed input. A broken hook that blocks all editing is a far
worse failure than a missed guard, and the guard is a speed bump, not a security
boundary.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# (pattern, why it is restricted)
RESTRICTED: list[tuple[str, str]] = [
    (r'(^|/)\.env($|\.)', 'configuration and three all-or-nothing credentials'),
    (r'storage-state.*\.json$', 'a live logged-in browser session'),
    (r'(^|/)config\.py$', 'the typed settings surface — every env var is declared here once'),
    (r'(^|/)harry/(registry|sdk)\.py$', 'the module contract every module is written against'),
    (r'(^|/)CLAUDE\.md$', 'the instructions this agent runs on'),
    (r'(^|/)\.claude/(rules|hooks|agents)/', 'the rules and guards themselves'),
]

# Anchored to this script's own location rather than the process working directory: the
# hook is invoked with whatever cwd the tool happened to leave behind, and a flag that
# resolves differently depending on that is worse than no flag at all.
UNLOCK_FLAG = Path(__file__).resolve().parent.parent / '.unlock-safety'


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        file_path = str(payload['tool_input']['file_path'])
    except Exception:
        # Malformed payload, unknown tool shape, empty stdin — allow and move on.
        return 0

    if UNLOCK_FLAG.exists():
        return 0

    for pattern, label in RESTRICTED:
        if re.search(pattern, file_path):
            sys.stderr.write(
                f'\n🛑 Blocked edit to restricted path: {file_path}\n'
                f'   Reason: {label}.\n'
                f'   Changing this should be deliberate — record why, then unlock:\n'
                f'       touch {UNLOCK_FLAG}\n'
                f'   and remove the flag once the change is committed.\n'
            )
            return 2

    return 0


if __name__ == '__main__':
    sys.exit(main())
