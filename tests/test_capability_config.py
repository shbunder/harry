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


def test_an_exported_key_in_this_machine_s_file_is_read_like_a_plain_one(capability):
    """`export KEY=value` is how an operator writes a file they also `source` by hand, and both
    readers of the root pair strip it. This reader did not: every connector on the NUC written
    that way resolved to its defaults, and a credential that was right there read as missing."""
    folder = capability('URL=https://committed.test\n', local='export URL=https://mine.test\nexport  USERNAME="me"\n')
    resolved = resolve(folder)
    assert resolved['url'] == 'https://mine.test'
    assert resolved['username'] == 'me'


def test_a_key_that_merely_starts_with_export_is_not_mistaken_for_one(capability):
    """Only `export` followed by whitespace is the prefix. `exporturl` is a key of its own, and
    stripping six characters from it would set `url` to a value nobody wrote."""
    folder = capability('exporturl=https://not-a-prefix.test\n')
    assert resolve(folder)['url'] == 'https://caldav.icloud.com'


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


# ---------------------------------------------------------------------------
# The mounted copy, for a container whose image carries no `.env.local`
# ---------------------------------------------------------------------------


@pytest.fixture
def mounted(tmp_path, monkeypatch):
    """A capability under a real-shaped root, and a settings directory laid out like `.harry/`.

    The capability sits at `<tmp>/.harry/connectors/icloud` rather than `<tmp>/icloud`, because
    the mounted file is found from the folder's parent's name — a test that put it anywhere
    else would prove a mapping production never takes.
    """
    import harry.config

    for name in SCHEMA:
        monkeypatch.delenv(env_key('icloud', name), raising=False)
    settings_dir = tmp_path / 'settings'
    monkeypatch.setenv('HARRY_CAPABILITY_SETTINGS_DIR', str(settings_dir))
    monkeypatch.setenv('HARRY_DATA_DIR', str(tmp_path / 'data'))
    harry.config.get_settings.cache_clear()

    def write(beside: str | None = None, there: str | None = None, kind: str = 'connectors', name: str = 'icloud'):
        folder = tmp_path / '.harry' / kind / name
        folder.mkdir(parents=True, exist_ok=True)
        if beside is not None:
            (folder / '.env.local').write_text(textwrap.dedent(beside), encoding='utf-8')
        if there is not None:
            (settings_dir / kind / name).mkdir(parents=True, exist_ok=True)
            (settings_dir / kind / name / '.env.local').write_text(textwrap.dedent(there), encoding='utf-8')
        return folder

    yield write
    harry.config.get_settings.cache_clear()


def test_the_mounted_file_beats_the_one_beside_the_capability(mounted):
    """In the container there is never a file beside the capability, so this order only
    matters on a machine that has both — and there, setting the directory was deliberate."""
    folder = mounted(beside='USERNAME=beside\n', there='USERNAME=mounted\n')
    assert resolve(folder)['username'] == 'mounted'


def test_the_mounted_file_is_how_a_container_gets_a_credential_at_all(mounted):
    """The whole point: the image has nothing beside the capability, and this still resolves."""
    folder = mounted(there='USERNAME=me@example.com\nAPP_PASSWORD=abcd-efgh-ijkl-mnop\n')
    assert resolve(folder)['app_password'] == 'abcd-efgh-ijkl-mnop'


def test_the_environment_still_beats_the_mounted_file(mounted, monkeypatch):
    folder = mounted(there='URL=https://mounted.test\n')
    monkeypatch.setenv(env_key('icloud', 'url'), 'https://injected.test')
    assert resolve(folder)['url'] == 'https://injected.test'


def test_a_person_s_own_file_still_beats_the_mounted_file(mounted, tmp_path):
    from harry.config import OWNER, user_data_dir

    folder = mounted(there='USERNAME=the-instance\n')
    own = user_data_dir(OWNER) / 'connectors' / 'icloud.env'
    own.parent.mkdir(parents=True)
    own.write_text('USERNAME=renee\n', encoding='utf-8')

    assert read_capability_config(folder, 'icloud', SCHEMA, principal=OWNER)['username'] == 'renee'
    assert resolve(folder)['username'] == 'the-instance'


def test_with_the_setting_empty_nothing_is_read_from_where_the_mount_would_be(mounted, monkeypatch):
    """A laptop resolves exactly as it did before the setting existed."""
    import harry.config

    folder = mounted(beside='USERNAME=beside\n', there='USERNAME=mounted\n')
    monkeypatch.setenv('HARRY_CAPABILITY_SETTINGS_DIR', '')
    harry.config.get_settings.cache_clear()

    assert resolve(folder)['username'] == 'beside'


def test_only_env_local_is_read_from_the_mounted_directory(mounted, tmp_path):
    """The committed `.env` travels in the image with the declaration it was generated from.
    A second copy out of a checkout on another commit must not be able to overrule it."""
    folder = mounted()
    (folder / '.env').write_text('URL=https://from-the-image.test\n', encoding='utf-8')
    (tmp_path / 'settings' / 'connectors' / 'icloud').mkdir(parents=True)
    (tmp_path / 'settings' / 'connectors' / 'icloud' / '.env').write_text('URL=https://from-the-checkout.test\n')

    assert resolve(folder)['url'] == 'https://from-the-image.test'


def test_a_connector_and_a_tool_with_one_name_read_different_mounted_files(mounted):
    """The kind's folder is part of the path, as it is under `.harry/`."""
    connector = mounted(there='USERNAME=the-connector\n', kind='connectors')
    tool = mounted(there='USERNAME=the-tool\n', kind='tools')

    assert resolve(connector)['username'] == 'the-connector'
    assert resolve(tool)['username'] == 'the-tool'


CREDENTIALED = """\
---
name: vault
description: A connector that cannot start without its token
expires: manual
enabled: true
config:
  token:
    description: The token
    required: true
    secret: true
---

Nothing to renew.
"""


def test_through_the_loader_a_connector_whose_credential_is_only_mounted_loads(mounted, tmp_path, monkeypatch):
    """The path production takes: `load()` resolves settings, then refuses or registers.

    Loaded with the directory named, skipped naming its setting without — the same folder,
    the same mounted file, one environment variable apart.
    """
    import harry.config
    from harry.loader import load
    from harry.registry import LOADED, SKIPPED

    monkeypatch.delenv(env_key('vault', 'token'), raising=False)
    folder = mounted(kind='connectors', name='vault', there='TOKEN=a-mounted-token-value\n')
    (folder / 'CONNECTOR.md').write_text(CREDENTIALED, encoding='utf-8')
    root = tmp_path / '.harry'

    found = load(roots=[root]).get('connector', 'vault')
    assert found is not None and found.status == LOADED, found and found.reason
    assert found.context is not None and found.context.config['token'] == 'a-mounted-token-value'

    monkeypatch.setenv('HARRY_CAPABILITY_SETTINGS_DIR', '')
    harry.config.get_settings.cache_clear()
    found = load(roots=[root]).get('connector', 'vault')
    assert found is not None and found.status == SKIPPED
    assert found.reason == 'required setting token is not set'
