"""Holds on for a moment, so a second fire arrives while the first is still going."""

import time
from harry.sdk import Context, Registry

STARTED = 'started.txt'


def register(registry: Registry, context: Context) -> None:
    @registry.job
    def slowpoke() -> None:
        with (context.folder / STARTED).open('a', encoding='utf-8') as handle:
            handle.write('in\n')
        time.sleep(0.6)
