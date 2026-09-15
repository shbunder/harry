"""A tablet that remembers rather than delivers."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from _plan import plan, refuse  # noqa: E402

from harry.sdk import Context, Registry  # noqa: E402


class Tablet:
    def __init__(self) -> None:
        self.pushed: list[tuple[str, str]] = []

    def push(self, path, name: str) -> dict:
        refuse(plan('remarkable'))
        self.pushed.append((str(path), name))
        return {'where': 'Daily', 'id': 'doc-1', 'name': name, 'replaced': 0}


def register(registry: Registry, context: Context) -> None:
    registry.connector(Tablet())
