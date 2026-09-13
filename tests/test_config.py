"""The two env files, and which one wins.

The precedence is the whole reason there are two files, and a precedence that is only
described in a comment is the control `.claude/rules/inert-controls.md` forbids. These
tests make it happen rather than assert that it is configured.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harry.config import ENV_FILES, Settings, get_settings

COMMITTED = 'HARRY_PORT=7430\nHARRY_LOG_LEVEL=INFO\nHARRY_API_TOKEN=\n'


def settings_from(*files: Path) -> Settings:
    """Build Settings from a specific pair of files.

    `_env_file` is a real pydantic-settings init argument but it is not on the generated
    `__init__` signature, so the checker cannot see it. One wrapper carries the one
    ignore rather than every call site carrying its own.
    """
    return Settings(_env_file=files)  # type: ignore[call-arg]  # pydantic-settings runtime kwarg


@pytest.fixture
def env_pair(tmp_path):
    """A `.env` / `.env.local` pair in a throwaway directory, read in that order."""

    def build(local: str = '') -> Settings:
        (tmp_path / '.env').write_text(COMMITTED, encoding='utf-8')
        (tmp_path / '.env.local').write_text(local, encoding='utf-8')
        return settings_from(tmp_path / '.env', tmp_path / '.env.local')

    return build


def test_the_committed_file_supplies_the_default(env_pair, monkeypatch):
    monkeypatch.delenv('HARRY_PORT', raising=False)
    settings = env_pair()
    assert settings.port == 7430


def test_this_machine_overrides_the_committed_file(env_pair, monkeypatch):
    """The point of the pair. A port set in `.env.local` beats the one in `.env`."""
    monkeypatch.delenv('HARRY_PORT', raising=False)
    settings = env_pair('HARRY_PORT=7431\n')
    assert settings.port == 7431


def test_a_key_absent_from_the_machine_file_still_comes_from_the_committed_one(env_pair, monkeypatch):
    """`.env.local` holds only what differs — it is not a copy, and it must not have to be."""
    monkeypatch.delenv('HARRY_PORT', raising=False)
    monkeypatch.delenv('HARRY_LOG_LEVEL', raising=False)
    settings = env_pair('HARRY_PORT=7431\n')
    assert settings.port == 7431
    assert settings.log_level == 'INFO'


def test_a_real_environment_variable_beats_both(env_pair, monkeypatch):
    """A command-line override is meant to win: `HARRY_PORT=7499 make serve`."""
    monkeypatch.setenv('HARRY_PORT', '7499')
    settings = env_pair('HARRY_PORT=7431\n')
    assert settings.port == 7499


def test_a_missing_machine_file_is_normal(tmp_path, monkeypatch):
    """A fresh clone has no `.env.local`, and must still start."""
    monkeypatch.delenv('HARRY_PORT', raising=False)
    (tmp_path / '.env').write_text(COMMITTED, encoding='utf-8')
    assert settings_from(tmp_path / '.env', tmp_path / '.env.local').port == 7430


def test_the_files_are_read_in_the_documented_order():
    """Later wins, so the machine's file must come second. Reversing this tuple is the
    one edit that silently makes `.env.local` do nothing."""
    assert [path.name for path in ENV_FILES] == ['.env', '.env.local']


def test_the_files_resolve_against_the_working_directory(tmp_path, monkeypatch):
    """What makes a worktree work.

    A worktree shares the primary checkout's virtual environment, so `harry` is imported
    from the primary tree however you got there. Anchoring the env files to the installed
    package would make every worktree read the primary tree's `.env.local` — the port and
    data directory `make worktree` wrote would be read by nothing, and two stacks would
    fight over one SQLite file while the configuration looked right.
    """
    monkeypatch.delenv('HARRY_PORT', raising=False)
    (tmp_path / '.env').write_text(COMMITTED, encoding='utf-8')
    (tmp_path / '.env.local').write_text('HARRY_PORT=7433\n', encoding='utf-8')

    monkeypatch.chdir(tmp_path)
    assert Settings().port == 7433


def test_a_key_a_module_owns_does_not_stop_core_starting(env_pair, monkeypatch):
    """`.env` carries every module's keys. Core has never heard of most of them."""
    monkeypatch.delenv('HARRY_PORT', raising=False)
    settings = env_pair('SLACK_BOT_TOKEN=xoxb-not-real\nHARRY_FUTURE_THING=1\n')
    assert settings.port == 7430


def test_the_secret_does_not_print_itself(env_pair, monkeypatch):
    """A token that renders in a log line, a span or a traceback is the whole failure."""
    monkeypatch.delenv('HARRY_API_TOKEN', raising=False)
    settings = env_pair('HARRY_API_TOKEN=super-secret-value\n')
    assert 'super-secret-value' not in repr(settings)
    assert 'super-secret-value' not in str(settings.api_token)
    assert settings.api_token.get_secret_value() == 'super-secret-value'


def test_the_mcp_url_follows_the_port(env_pair, monkeypatch):
    """The NUC's `claude -p` call never leaves the machine, whatever the port is."""
    monkeypatch.delenv('HARRY_PORT', raising=False)
    settings = env_pair('HARRY_PORT=7431\n')
    assert settings.mcp_url == 'http://localhost:7431/mcp'


def test_the_repo_env_file_is_real_configuration(monkeypatch):
    """The committed `.env` is configuration, not a sample. 06:30 is a local time, and a
    timezone that silently fell back to a default would move the morning page.

    Reads `.env` **alone**, deliberately. An earlier version read the pair and asserted
    `port == 7430`, which passed in the primary checkout and failed in the first worktree
    that ever ran it — because `make worktree` writes `HARRY_PORT=7431` into that tree's
    `.env.local` on purpose, so two stacks do not fight over one port. The test was
    asserting a global constant against the one setting the design guarantees is local.
    """
    repo = Path(__file__).parent.parent
    if not (repo / '.env').exists():
        pytest.skip('no committed .env in this tree')

    monkeypatch.delenv('HARRY_LOCATION_TZ', raising=False)
    monkeypatch.delenv('HARRY_PORT', raising=False)
    settings = settings_from(repo / '.env')
    assert settings.timezone == 'Europe/Brussels'
    # `== 7430`, not `> 0`. Reading `.env` alone is what fixed the worktree failure, and
    # once it reads that file alone a worktree's 7431 cannot leak in — so the strict
    # assertion was correct all along and `> 0` weakened it for nothing. `> 0` also
    # passes when the file has no HARRY_PORT line at all, because the field defaults to
    # 7430, which makes it a test of the default rather than of the file.
    assert settings.port == 7430


# ---------------------------------------------------------------------------
# The entry point
# ---------------------------------------------------------------------------


def test_running_harry_uses_the_configured_port_not_a_hardcoded_one(tmp_path, monkeypatch):
    """The claim that one place decides the port, made to fail if it stops being true.

    Both the Makefile and the Dockerfile dropped their `--port` flags for this. If the
    entry point ever hardcodes one again, a worktree's `.env.local` would set a port that
    nothing binds — and every symptom would point at the worktree instead.
    """
    import harry.__main__ as entry

    monkeypatch.delenv('HARRY_PORT', raising=False)
    (tmp_path / '.env').write_text(COMMITTED, encoding='utf-8')
    (tmp_path / '.env.local').write_text('HARRY_PORT=7434\nHARRY_LOG_LEVEL=WARNING\n', encoding='utf-8')
    monkeypatch.chdir(tmp_path)
    get_settings.cache_clear()

    called: dict = {}

    def fake_run(app, **kwargs):
        called['app'] = app
        called.update(kwargs)

    import uvicorn

    monkeypatch.setattr(uvicorn, 'run', fake_run)

    assert entry.main([]) == 0
    assert called['app'] == 'harry.main:app'
    assert called['port'] == 7434
    assert called['log_level'] == 'warning'
    assert called['reload'] is False

    assert entry.main(['--reload']) == 0
    assert called['reload'] is True

    get_settings.cache_clear()


def test_every_key_the_committed_env_leaves_empty_resolves_to_empty(monkeypatch):
    """The bug this exists for: an inline comment after an EMPTY value becomes the value.

    `HARRY_API_TOKEN=   # generate with openssl` resolved to the string
    "# generate with openssl", so an unconfigured Harry had a bearer token — published
    in this file, in this repository. `HARRY_CAPABILITIES_DIR=` became `Path('.')`, which
    would have loaded the whole working directory as capabilities.

    Neither failed anything. Both looked configured and were wrong, which is why this
    asserts the resolved values rather than the file's shape.
    """
    repo = Path(__file__).parent.parent
    if not (repo / '.env').exists():
        pytest.skip('no committed .env in this tree')

    for name in ('HARRY_API_TOKEN', 'HARRY_PUBLIC_URL', 'HARRY_CAPABILITIES_DIR'):
        monkeypatch.delenv(name, raising=False)

    settings = settings_from(repo / '.env')
    assert settings.api_token.get_secret_value() == '', 'an unset token must authorise nobody'
    assert settings.public_url is None
    assert settings.capabilities_dir is None
