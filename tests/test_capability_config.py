"""A capability's settings, and the four layers they come from.

The layering is the whole reason there are two files per capability, and a layering that
only exists in a comment is the control `.claude/rules/inert-controls.md` describes. Each
layer is made to win here, and each is made to lose.
"""

from __future__ import annotations

import textwrap

import pytest

import env_template
from harry.config import capability_env_files, env_key, read_capability_config

SCHEMA = {
    'username': {'description': 'Your Apple ID', 'required': True},
    'app_password': {'description': 'App-specific password', 'secret': True, 'required': True},
    'article_limit': {'description': '6-8 is a readable morning', 'default': 8},
    'url': {'description': 'The CalDAV endpoint', 'default': 'https://caldav.icloud.com'},
}


@pytest.fixture
def capability(tmp_path, monkeypatch):
    """A capability folder, and a way to write either half of its pair."""
    folder = tmp_path / 'icloud'
    folder.mkdir()
    for name in SCHEMA:
        monkeypatch.delenv(env_key('icloud', name), raising=False)

    def write(committed: str = '', local: str | None = None):
        (folder / '.env').write_text(textwrap.dedent(committed), encoding='utf-8')
        if local is not None:
            (folder / '.env.local').write_text(textwrap.dedent(local), encoding='utf-8')
        return folder

    return write


def resolve(folder):
    return read_capability_config(folder, 'icloud', SCHEMA)


# ---------------------------------------------------------------------------
# The four layers, each made to win
# ---------------------------------------------------------------------------


def test_a_declared_default_applies_with_no_files_at_all(tmp_path):
    """A fresh capability with nothing configured still starts on its defaults."""
    folder = tmp_path / 'icloud'
    folder.mkdir()
    assert resolve(folder) == {'article_limit': 8, 'url': 'https://caldav.icloud.com'}


def test_the_committed_file_beats_the_default(capability):
    folder = capability('URL=https://example.test\n')
    assert resolve(folder)['url'] == 'https://example.test'


def test_this_machine_beats_the_committed_file(capability):
    """The point of the pair, one level down from the root."""
    folder = capability('URL=https://committed.test\n', local='URL=https://mine.test\n')
    assert resolve(folder)['url'] == 'https://mine.test'


def test_the_environment_beats_both(capability, monkeypatch):
    """How a container injects a setting — it has no folders, only a flat environment."""
    folder = capability('URL=https://committed.test\n', local='URL=https://mine.test\n')
    monkeypatch.setenv(env_key('icloud', 'url'), 'https://injected.test')
    assert resolve(folder)['url'] == 'https://injected.test'


# ---------------------------------------------------------------------------
# The rules that stop a layer winning when it should not
# ---------------------------------------------------------------------------


def test_an_empty_value_is_an_unset_key_not_an_override(capability):
    """The generated file leaves every secret blank. If empty overrode, generating the
    template would wipe out the defaults it was generated from, and `ARTICLE_LIMIT=`
    would resolve to the empty string rather than 8."""
    folder = capability('ARTICLE_LIMIT=\nAPP_PASSWORD=\nURL=\n')
    resolved = resolve(folder)
    assert resolved['article_limit'] == 8
    assert resolved['url'] == 'https://caldav.icloud.com'
    assert 'app_password' not in resolved


def test_a_key_the_capability_never_declared_is_ignored(capability):
    """Either a typo or a leftover. Honouring it silently is how a setting nobody can
    find takes effect."""
    folder = capability('USERNAME=me\nSMTP_SERVER=oops\n')
    assert 'smtp_server' not in resolve(folder)
    assert resolve(folder)['username'] == 'me'


def test_keys_in_a_capability_file_are_bare(capability):
    """The folder is the namespace, so the prefix would be ceremony. A prefixed key in
    the file is a key nothing reads — worth failing on rather than ignoring silently."""
    folder = capability('HARRY_ICLOUD_USERNAME=prefixed\n')
    assert 'username' not in resolve(folder)

    folder = capability('USERNAME=bare\n')
    assert resolve(folder)['username'] == 'bare'


def test_a_missing_required_setting_simply_is_not_there(capability):
    """So the caller can disable the capability and say which key is missing, rather
    than starting with an empty credential and failing at 06:30."""
    folder = capability('ARTICLE_LIMIT=6\n')
    resolved = resolve(folder)
    assert 'username' not in resolved
    assert 'app_password' not in resolved


def test_the_pair_is_read_in_the_documented_order(tmp_path):
    """Reversing this tuple is the one edit that silently makes .env.local do nothing."""
    assert [p.name for p in capability_env_files(tmp_path)] == ['.env', '.env.local']


def test_comments_and_blank_lines_do_not_become_settings(capability):
    folder = capability('# a comment\n\n  \nUSERNAME=me\n')
    assert resolve(folder) == {
        'article_limit': 8,
        'url': 'https://caldav.icloud.com',
        'username': 'me',
    }


# ---------------------------------------------------------------------------
# The generated file
# ---------------------------------------------------------------------------


DECLARATION = """\
---
name: icloud
description: Apple calendar and reminders over CalDAV
expires: manual
enabled: true
config:
  username:
    description: Your Apple ID
    required: true
  app_password:
    description: App-specific password from appleid.apple.com
    secret: true
    required: true
  url:
    description: The CalDAV endpoint
    default: https://caldav.icloud.com
---

How to renew it.
"""


@pytest.fixture
def harry_tree(tmp_path, monkeypatch):
    root = tmp_path / '.harry'
    (root / 'connectors' / 'icloud').mkdir(parents=True)
    (root / 'connectors' / 'icloud' / 'CONNECTOR.md').write_text(DECLARATION, encoding='utf-8')
    monkeypatch.setattr(env_template, 'ROOT', tmp_path)
    monkeypatch.setattr(env_template, 'HARRY', root)
    return root / 'connectors' / 'icloud'


def test_the_template_is_generated_from_the_declaration(harry_tree, capsys):
    assert env_template.main([]) == 0
    written = (harry_tree / '.env').read_text()

    assert 'USERNAME=' in written
    assert 'Your Apple ID' in written
    assert 'URL=https://caldav.icloud.com' in written  # a default is rendered
    assert 'APP_PASSWORD=\n' in written  # a secret never is
    assert 'SECRET' in written
    assert 'override: HARRY_ICLOUD_URL' in written  # the container's spelling
    assert 'Do not edit this file' in written


def test_a_stale_template_fails_the_check(harry_tree, capsys):
    """This is what stops the committed file drifting from the schema. Without it the
    description beside a key is true only until somebody changes the declaration."""
    assert env_template.main(['--check']) == 1
    assert 'missing' in capsys.readouterr().err

    env_template.main([])
    assert env_template.main(['--check']) == 0

    (harry_tree / '.env').write_text('USERNAME=\n', encoding='utf-8')
    assert env_template.main(['--check']) == 1
    assert 'out of date' in capsys.readouterr().err


def test_what_is_generated_resolves_to_the_declared_defaults(harry_tree):
    """The generated file and the resolver have to agree, or every fresh capability
    starts with settings nobody chose."""
    env_template.main([])
    schema = {
        'username': {'description': 'x', 'required': True},
        'app_password': {'description': 'y', 'secret': True, 'required': True},
        'url': {'description': 'z', 'default': 'https://caldav.icloud.com'},
    }
    assert read_capability_config(harry_tree, 'icloud', schema) == {'url': 'https://caldav.icloud.com'}
