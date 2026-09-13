"""Reaches into core. The loader must refuse this before executing a line of it."""

from pathlib import Path

# A tripwire, deliberately before the forbidden import: if this file is ever executed,
# the marker appears and the test that says "and the module is never executed" fails.
Path(__file__).with_name('IT-RAN').write_text('it ran', encoding='utf-8')

import harry.scheduler  # noqa: E402, F401
