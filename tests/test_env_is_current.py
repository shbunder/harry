"""`.env` still describes the Harry that exists.

`.env` is committed, so it is documentation that ships — and documentation that ships is
documentation that goes stale. Two architectural decisions have since retired keys that
are still in it, and a reader who trusts the file would configure something that nothing
reads.

One test, one list, one round trip. Every entry names the fix.
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent

# key -> what to do about it, and why.
RETIRED = {
    'ANTHROPIC_API_KEY': 'delete — Harry never calls a model (ADR-260912-bd36c2)',
    'HARRY_CLAUDE_BIN': 'delete — Harry ships no model CLI (ADR-260912-bd36c2)',
    'HARRY_CLAUDE_MCP_URL': 'delete — nothing in Harry dials a model (ADR-260912-bd36c2)',
    'HARRY_DIGEST_CRON': 'replace with HARRY_DIGEST_DEADLINE=07:00 — a Claude scheduled task '
    'owns the clock now, and what Harry needs is a deadline for the watchdog. '
    "A job's own schedule lives in its JOB.md (ADR-260912-399f07)",
    'HARRY_MODULES_DIR': 'rename to HARRY_CAPABILITIES_DIR — modules became connectors, '
    'tools and jobs (ADR-260912-399f07)',
    # Settings that belong to one capability, not to everybody. Each moves into that
    # implementation's `config:` block, where it gets a default and a description, and is
    # read from a derived key — HARRY_<IMPLEMENTATION>_<SETTING>.
    'HARRY_ARTICLE_LIMIT': 'move to the morning-page job as config.article_limit (default 8)',
    'HARRY_NEWS_INTERESTS': 'move to the morning-page job as config.interests',
    'HARRY_NEWS_FEEDS': 'move to the news connector as config.feeds',
    'HARRY_LOCATION_LAT': 'move to the weather connector as config.lat',
    'HARRY_LOCATION_LON': 'move to the weather connector as config.lon',
    'TIJD_STORAGE_STATE': 'becomes HARRY_TIJD_STORAGE_STATE, declared by the tijd connector',
    'ICLOUD_USERNAME': 'becomes HARRY_ICLOUD_USERNAME, declared by the icloud connector',
    'ICLOUD_APP_PASSWORD': 'becomes HARRY_ICLOUD_APP_PASSWORD, declared by the icloud connector',
    'ICLOUD_CALENDARS': 'becomes HARRY_ICLOUD_CALENDARS, declared by the icloud connector',
    'REMARKABLE_DEVICE_TOKEN': 'becomes HARRY_REMARKABLE_DEVICE_TOKEN, declared by the remarkable connector',
    'REMARKABLE_FOLDER': 'becomes HARRY_REMARKABLE_FOLDER, declared by the remarkable connector',
    'SLACK_BOT_TOKEN': 'becomes HARRY_SLACK_BOT_TOKEN, declared by the slack connector',
    'SLACK_APP_TOKEN': 'becomes HARRY_SLACK_APP_TOKEN, declared by the slack connector',
    'SLACK_DEFAULT_CHANNEL': 'becomes HARRY_SLACK_DEFAULT_CHANNEL, declared by the slack connector',
}


def declared_keys() -> set[str]:
    path = ROOT / '.env'
    if not path.exists():
        pytest.skip('no .env in this tree')
    return {
        line.split('=', 1)[0].strip()
        for line in path.read_text(encoding='utf-8').splitlines()
        if '=' in line and not line.lstrip().startswith('#')
    }


def test_no_retired_key_is_still_declared():
    """The failure message is the instruction on purpose. `.env` is committed, so the fix
    lands once and this then guards against the keys coming back."""
    stale = sorted(declared_keys() & set(RETIRED))
    if not stale:
        return

    lines = '\n'.join(f'    {key}\n        {RETIRED[key]}' for key in stale)
    pytest.fail(
        f'\n\n{len(stale)} key(s) in .env describe a design that no longer exists:\n\n{lines}\n\n'
        'Also delete the "---- Claude Code on the NUC ----" block header and its comment,\n'
        'which explains a trigger Harry no longer owns.\n\n'
        'Most of these are not deletions but relocations: a setting belongs to the capability\n'
        'that reads it, declared in its `config:` block with a description and a default.\n'
        'They move as each capability is built, not all at once. What is left in .env is\n'
        "core's own six keys, and the generated template rebuilds the rest.\n",
        pytrace=False,
    )


def test_the_keys_the_current_design_needs_are_present():
    """The other direction, which nothing else checks: a setting the code reads and the
    committed file never mentions is one nobody knows exists."""
    required = {'HARRY_PORT', 'HARRY_DATA_DIR', 'HARRY_API_TOKEN', 'HARRY_LOCATION_TZ'}
    missing = sorted(required - declared_keys())
    assert not missing, f'declared in config.py but absent from .env: {", ".join(missing)}'
