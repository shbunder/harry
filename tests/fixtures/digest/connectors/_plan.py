"""What the three digest stand-ins do, read from one JSON file.

The behaviour a test wants differs per test — answers, raises, or is absent — and a fixture
that can only do one thing needs three folders per case. `HARRY_DIGEST_TEST_PLAN` names a
file; each stand-in reads its own key out of it.
"""

from __future__ import annotations

import json
import os
from typing import Any


def plan(name: str) -> dict[str, Any]:
    where = os.environ.get('HARRY_DIGEST_TEST_PLAN')
    if not where:
        return {}
    with open(where, encoding='utf-8') as file:
        return json.load(file).get(name) or {}


def refuse(how: dict[str, Any]) -> None:
    """Raise what the plan asked for, if it asked for anything."""
    if how.get('raises'):
        raise RuntimeError(how['raises'])
