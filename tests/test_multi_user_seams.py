"""The seams for things not built yet: a second instance, and a second person.

Both retrofits are the expensive kind — a loader hard-wired to one directory, and tool
calls with no caller. These tests hold the plural shape in place so Phase 1 cannot write
code that assumes one of either.

They are testing machinery with one real caller today. That is the point, and it is also
the risk: machinery nobody exercises rots. So each one exercises the plural path, not the
singular one.
"""

from __future__ import annotations

import pytest
from pydantic import SecretStr

from harry.config import (
    OWNER,
    Principal,
    Settings,
    capability_roots,
    principal_for_token,
    read_capability_config,
    user_data_dir,
)

SCHEMA = {
    'username': {'description': 'the account'},
    'url': {'description': 'the endpoint', 'default': 'https://caldav.icloud.com'},
}


@pytest.fixture
def settings(monkeypatch):
    """Replace the cached settings, so nothing here reads the real .env pair."""

    def build(**kwargs):
        import harry.config

        made = Settings(**kwargs)
        monkeypatch.setattr(harry.config, 'get_settings', lambda: made)
        return made

    return build


# ---------------------------------------------------------------------------
# A second instance: the loader takes a list, and later wins
# ---------------------------------------------------------------------------


def test_roots_are_a_list_in_load_order(settings, tmp_path, monkeypatch):
    """Bundled, then the instance, then an extra directory. Order is the whole contract:
    later wins on name, which is how an instance swaps out a bundled connector without
    forking anything."""
    import harry.config

    bundled = tmp_path / 'bundled'
    instance = tmp_path / 'instance' / '.harry'
    extra = tmp_path / 'extra'
    for d in (bundled, instance, extra):
        d.mkdir(parents=True)

    settings(capabilities_dir=extra)
    monkeypatch.setattr(harry.config, 'BUNDLED_CAPABILITIES', bundled)
    monkeypatch.chdir(instance.parent)

    assert capability_roots() == [bundled.resolve(), instance.resolve(), extra.resolve()]


def test_a_root_that_does_not_exist_is_skipped_not_fatal(settings, tmp_path, monkeypatch):
    """Bundled is empty today and `$HARRY_CAPABILITIES_DIR` is usually unset. Neither is
    an error — a missing root is a root with nothing in it."""
    import harry.config

    instance = tmp_path / '.harry'
    instance.mkdir()
    settings(capabilities_dir=tmp_path / 'does-not-exist')
    monkeypatch.setattr(harry.config, 'BUNDLED_CAPABILITIES', tmp_path / 'also-missing')
    monkeypatch.chdir(tmp_path)

    assert capability_roots() == [instance.resolve()]


def test_an_extra_root_comes_after_the_instance(settings, tmp_path, monkeypatch):
    """So `$HARRY_CAPABILITIES_DIR` can override the instance, not the other way round."""
    import harry.config

    instance = tmp_path / '.harry'
    extra = tmp_path / 'extra'
    for d in (instance, extra):
        d.mkdir()
    settings(capabilities_dir=extra)
    monkeypatch.setattr(harry.config, 'BUNDLED_CAPABILITIES', tmp_path / 'nope')
    monkeypatch.chdir(tmp_path)

    roots = capability_roots()
    assert roots.index(extra.resolve()) > roots.index(instance.resolve())


# ---------------------------------------------------------------------------
# A second person: every call has a principal
# ---------------------------------------------------------------------------


def test_the_configured_token_resolves_to_the_owner(settings):
    settings(api_token=SecretStr('the-real-one'))
    assert principal_for_token('the-real-one') == OWNER


def test_an_unrecognised_token_resolves_to_nobody(settings):
    """Not to the owner. A wrong token is not a quieter version of the right one."""
    settings(api_token=SecretStr('the-real-one'))
    assert principal_for_token('someone-elses') is None
    assert principal_for_token('') is None


def test_an_unset_token_authorises_nobody(settings):
    """The dangerous default. An empty configured token must not mean 'anything matches' —
    that is how an unconfigured Harry behind a tunnel serves the internet."""
    settings(api_token=SecretStr(''))
    assert principal_for_token('') is None
    assert principal_for_token('anything') is None


def test_each_person_gets_their_own_directory_under_the_data_volume(settings, tmp_path):
    """Under the data volume, never the repository. Other people's credentials are not
    something to commit, and a directory boundary cannot be got wrong the way a rule can."""
    settings(data_dir=tmp_path)
    assert user_data_dir(OWNER) == tmp_path / 'users' / 'owner'
    assert user_data_dir(Principal(id='renee', name='Renée')) == tmp_path / 'users' / 'renee'


# ---------------------------------------------------------------------------
# The two seams meeting: whose credential?
# ---------------------------------------------------------------------------


def test_a_persons_own_setting_beats_the_instances(settings, tmp_path, monkeypatch):
    """What makes "whose calendar?" answerable. Two people, one connector, one machine."""
    monkeypatch.delenv('HARRY_ICLOUD_USERNAME', raising=False)
    settings(data_dir=tmp_path / 'data')

    folder = tmp_path / 'icloud'
    folder.mkdir()
    (folder / '.env.local').write_text('USERNAME=the-owner@example.com\n', encoding='utf-8')

    renee = Principal(id='renee', name='Renée')
    hers = user_data_dir(renee) / 'connectors'
    hers.mkdir(parents=True)
    (hers / 'icloud.env').write_text('USERNAME=renee@example.com\n', encoding='utf-8')

    assert read_capability_config(folder, 'icloud', SCHEMA)['username'] == 'the-owner@example.com'
    assert read_capability_config(folder, 'icloud', SCHEMA, principal=renee)['username'] == 'renee@example.com'


def test_a_person_falls_back_to_the_instance_for_what_they_have_not_set(settings, tmp_path, monkeypatch):
    """A person's file holds only what differs, the same as every other layer here."""
    monkeypatch.delenv('HARRY_ICLOUD_USERNAME', raising=False)
    monkeypatch.delenv('HARRY_ICLOUD_URL', raising=False)
    settings(data_dir=tmp_path / 'data')

    folder = tmp_path / 'icloud'
    folder.mkdir()
    (folder / '.env').write_text('URL=https://shared.example.test\n', encoding='utf-8')

    renee = Principal(id='renee', name='Renée')
    hers = user_data_dir(renee) / 'connectors'
    hers.mkdir(parents=True)
    (hers / 'icloud.env').write_text('USERNAME=renee@example.com\n', encoding='utf-8')

    resolved = read_capability_config(folder, 'icloud', SCHEMA, principal=renee)
    assert resolved == {'username': 'renee@example.com', 'url': 'https://shared.example.test'}


def test_no_principal_reads_nothing_of_anyones(settings, tmp_path, monkeypatch):
    """The single-user path stays exactly what it was: a call with no principal never
    touches a user directory, so today's behaviour is unchanged by all of this."""
    monkeypatch.delenv('HARRY_ICLOUD_USERNAME', raising=False)
    settings(data_dir=tmp_path / 'data')

    folder = tmp_path / 'icloud'
    folder.mkdir()
    (folder / '.env.local').write_text('USERNAME=the-owner@example.com\n', encoding='utf-8')

    hers = user_data_dir(Principal(id='renee', name='Renée')) / 'connectors'
    hers.mkdir(parents=True)
    (hers / 'icloud.env').write_text('USERNAME=renee@example.com\n', encoding='utf-8')

    assert read_capability_config(folder, 'icloud', SCHEMA)['username'] == 'the-owner@example.com'
