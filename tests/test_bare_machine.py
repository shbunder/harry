"""A machine with nothing configured, which is where every NUC starts.

**A bare Harry is not an empty Harry, and that asymmetry is the whole test.** Weather and
news declare no required setting, so both load and their tools load with them. iCloud, the
tablet and Slack each declare one, so each is skipped naming what it is missing, and every
tool that `requires:` one of them is skipped naming the connector. The first page built on
a fresh machine therefore has a weather panel and headlines and no agenda.

The real `.harry/` tree, loaded through `build_app()` and read back over `/health` — the
way anything would ask. Fixtures would prove the loader works and say nothing about the
five connectors that actually ship, which are the things a first boot is about.

Two ways this machine could answer differently from a bare one, and both are closed here:
a `.env.local` beside a capability, which `copy_capability` leaves behind, and an exported
`HARRY_<CAPABILITY>_<SETTING>`, which outranks both dotenv files and is cleared below.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from harry.main import build_app

from .capability_copy import copy_capability

REPO = Path(__file__).parent.parent
HARRY = REPO / '.harry'

CONFIGURED_BY_THIS_MACHINE = re.compile(r'^HARRY_(WEATHER|NEWS|ICLOUD|REMARKABLE|SLACK|TIJD)_')
"""Anything a developer exported that would configure a connector this test wants bare.

Matched by prefix rather than listed key by key, so a setting added to a declaration
tomorrow is cleared without anyone remembering to come back here.
"""

LOADS_WITH_NOTHING_SET = {'weather', 'news'}
"""The two connectors whose every setting carries a default."""

SKIPPED_WITH_ITS_SETTING = {
    'icloud': ('username', 'app_password'),
    'remarkable': ('device_token',),
    'slack': ('bot_token', 'channel'),
    'tijd': ('email', 'password'),
}
"""The four that cannot work without a credential, and what each one asks for."""

SKIPPED_WITH_ITS_CONNECTOR = {
    'icloud_list_events': 'icloud',
    'remarkable_list_documents': 'remarkable',
    'remarkable_push_document': 'remarkable',
    'slack_post': 'slack',
}
"""Tools that `requires:` a connector that did not load."""

LOADS_ANYWAY = {'weather_forecast', 'news_search', 'news_article'}
"""Tools whose connector needs nothing, plus — separately — the two digest tools, which
name all four connectors under `optional:` and so load with none of them."""

DIGEST_TOOLS = {'digest_list_candidates', 'digest_build'}


@pytest.fixture
def bare(tmp_path, monkeypatch):
    """Harry started from a copy of the real `.harry/`, with nothing configured anywhere."""
    import harry.config

    for key in [key for key in os.environ if CONFIGURED_BY_THIS_MACHINE.match(key)]:
        monkeypatch.delenv(key, raising=False)
    # A mounted settings directory is this machine's credentials by another route.
    monkeypatch.delenv('HARRY_CAPABILITY_SETTINGS_DIR', raising=False)

    harry.config.get_settings.cache_clear()
    monkeypatch.setattr(harry.config, 'BUNDLED_CAPABILITIES', tmp_path / 'no-bundled')

    root = tmp_path / '.harry'
    for kind in ('connectors', 'tools', 'jobs'):
        for folder in sorted((HARRY / kind).iterdir()):
            if folder.is_dir():
                copy_capability(folder, root / kind / folder.name)

    monkeypatch.chdir(tmp_path)
    with TestClient(build_app()) as client:
        yield client.get('/health').json()
    harry.config.get_settings.cache_clear()


def rows(health: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row['name']: row for row in health['capabilities']}


# ---------------------------------------------------------------------------
# It comes up at all
# ---------------------------------------------------------------------------


def test_a_machine_with_no_credentials_still_answers(bare):
    """Nothing crashes: absent configuration disables a capability, it does not stop Harry."""
    assert bare['status'] == 'ok'
    assert bare['loaded'] > 0, 'a bare machine loaded nothing at all'


# ---------------------------------------------------------------------------
# Two of five work with nothing set
# ---------------------------------------------------------------------------


@pytest.mark.parametrize('name', sorted(LOADS_WITH_NOTHING_SET))
def test_a_connector_whose_settings_all_have_defaults_loads(bare, name):
    """Every setting weather and news declare carries a default, so a bare machine has both.

    This is the criterion that makes the first boot worth doing before any credential
    arrives. Give either of them a `required:` setting and this goes red.
    """
    row = rows(bare)[name]
    assert row['status'] == 'loaded', row.get('reason')


@pytest.mark.parametrize('name', sorted(LOADS_ANYWAY | DIGEST_TOOLS))
def test_a_tool_needing_no_credential_loads(bare, name):
    row = rows(bare)[name]
    assert row['status'] == 'loaded', row.get('reason')


# ---------------------------------------------------------------------------
# Three of five say what they are missing
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(('name', 'settings'), sorted(SKIPPED_WITH_ITS_SETTING.items()))
def test_a_connector_missing_a_credential_is_skipped_naming_the_setting(bare, name, settings):
    """Skipped, and the reason is the sentence somebody reads to fix it.

    Naming the setting is the point: "icloud: skipped" sends a person to the source, and
    "required settings app_password and username are not set" sends them to the file.
    """
    row = rows(bare)[name]
    assert row['status'] == 'skipped'
    for setting in settings:
        assert setting in row['reason'], f'{name} did not name {setting}: {row["reason"]}'


@pytest.mark.parametrize(('name', 'connector'), sorted(SKIPPED_WITH_ITS_CONNECTOR.items()))
def test_a_tool_whose_connector_is_missing_is_skipped_naming_the_connector(bare, name, connector):
    """A tool that required a skipped connector is skipped too, rather than registering and
    failing on its first call — which would read as a broken tool instead of an unset key."""
    row = rows(bare)[name]
    assert row['status'] == 'skipped'
    assert connector in row['reason'], f'{name} did not name {connector}: {row["reason"]}'


# ---------------------------------------------------------------------------
# Nothing else is quietly missing
# ---------------------------------------------------------------------------


def test_every_capability_in_the_tree_is_accounted_for(bare):
    """Loaded or skipped with a reason — never present and silent.

    The roster above is three hand-written dicts, and a hand-written roster is the thing
    `.claude/rules/inert-controls.md` warns about: add a connector to `.harry/` and this
    test is what notices it was never classified here.
    """
    classified = LOADS_WITH_NOTHING_SET | set(SKIPPED_WITH_ITS_SETTING) | LOADS_ANYWAY | DIGEST_TOOLS
    classified |= set(SKIPPED_WITH_ITS_CONNECTOR) | {'morning-page'}

    found = {row['name'] for row in bare['capabilities']}
    assert found == classified, f'unclassified: {sorted(found - classified)}; gone: {sorted(classified - found)}'

    for row in bare['capabilities']:
        assert row['status'] in {'loaded', 'skipped'}
        if row['status'] == 'skipped':
            assert row.get('reason'), f'{row["name"]} was skipped without saying why'
