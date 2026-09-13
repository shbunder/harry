"""What loaded, what did not, and why — over HTTP, the way anything would ask.

Every test here starts the real app and lets its start-up run, because the question is
what somebody gets when they call `/health` on a Harry that has just come up. Calling the
catalogue directly would answer a question nobody asks.
"""

from __future__ import annotations

import logging

import pytest
from fastapi.testclient import TestClient

from harry.main import build_app, configure_logging

from .test_loader import root_with


@pytest.fixture
def harry(tmp_path, monkeypatch):
    """A Harry whose `.harry/` is whatever the test puts in it.

    It goes through `capability_roots()` — chdir, no bundled directory, no extra one —
    rather than handing the loader a path, so the resolution production uses is the
    resolution under test.
    """
    import harry.config

    harry.config.get_settings.cache_clear()
    monkeypatch.setattr(harry.config, 'BUNDLED_CAPABILITIES', tmp_path / 'no-bundled')
    monkeypatch.chdir(tmp_path)

    class Build:
        """Prepare and start, separately.

        `build_app()` loads the capabilities, because the MCP server publishes them as
        routes and a route cannot appear after the app is serving. So a test that has to
        act in between — write a credential, attach a log handler — does it in two steps.
        """

        def prepare(self, *capabilities: str) -> None:
            root_with(tmp_path / '.harry', *capabilities)

        def start(self) -> TestClient:
            return TestClient(build_app())

        def __call__(self, *capabilities: str) -> TestClient:
            self.prepare(*capabilities)
            return self.start()

    yield Build()
    harry.config.get_settings.cache_clear()


def test_health_lists_every_capability_with_its_kind_and_status(harry):
    with harry('connectors/weather', 'tools/weather_forecast', 'jobs/refresh') as client:
        response = client.get('/health')

    assert response.status_code == 200
    body = response.json()
    rows = {row['name']: row for row in body['capabilities']}
    assert rows['weather']['kind'] == 'connector'
    assert rows['weather_forecast']['kind'] == 'tool'
    assert rows['refresh']['kind'] == 'job'
    assert {row['status'] for row in body['capabilities']} == {'loaded'}


def test_four_of_five_is_still_200(harry, monkeypatch):
    """Harry running with four of five is Harry running. A 503 here would train whoever
    is watching to ignore the number, and then the one that matters goes unread too."""
    monkeypatch.delenv('HARRY_ICLOUD_APP_PASSWORD', raising=False)
    with harry('connectors/weather', 'connectors/broken', 'connectors/icloud') as client:
        response = client.get('/health')

    assert response.status_code == 200
    body = response.json()
    assert body['status'] == 'ok'
    assert (body['loaded'], body['skipped']) == (1, 2)


def test_every_skipped_capability_carries_the_reason_it_was_skipped(harry, monkeypatch):
    """The whole point of the endpoint. "Two skipped" sends somebody to a log file;
    "ModuleNotFoundError: No module named …" is already the answer."""
    monkeypatch.delenv('HARRY_ICLOUD_APP_PASSWORD', raising=False)
    with harry('connectors/broken', 'connectors/icloud', 'connectors/nosy') as client:
        rows = {row['name']: row for row in client.get('/health').json()['capabilities']}

    assert 'a_dependency_nobody_installed' in rows['broken']['reason']
    assert rows['icloud']['reason'] == 'required setting app_password is not set'
    assert 'harry.scheduler' in rows['nosy']['reason']


def test_a_loaded_capability_carries_no_reason(harry):
    """A reason on something that worked is noise, and noise is what stops the column
    being read."""
    with harry('connectors/weather') as client:
        row = client.get('/health').json()['capabilities'][0]

    assert 'reason' not in row


def test_a_shadowed_capability_names_what_replaced_it(harry, tmp_path, monkeypatch):
    """Somebody wondering why their edit had no effect needs this, and a log line from a
    restart three weeks ago will not be there."""
    import harry.config as config

    bundled = root_with(tmp_path / 'bundled', 'connectors/weather')
    monkeypatch.setattr(config, 'BUNDLED_CAPABILITIES', bundled)

    with harry('connectors/weather') as client:
        rows = [row for row in client.get('/health').json()['capabilities'] if row['name'] == 'weather']

    shadowed = [row for row in rows if row['status'] == 'skipped']
    assert len(shadowed) == 1
    assert shadowed[0]['shadowed_by'].endswith('.harry/connectors/weather')
    assert [row for row in rows if row['status'] == 'loaded']


def test_the_response_names_no_secret_in_any_field(harry, tmp_path, monkeypatch):
    """Asserted against a capability that actually has one, and that puts it in the
    exception it raises — which is what people write when something has just gone wrong."""
    monkeypatch.delenv('HARRY_LEAKY_API_KEY', raising=False)
    secret = 'sk-live-9f3c7a21-do-not-log-me'

    harry.prepare('connectors/leaky', 'connectors/weather')
    (tmp_path / '.harry' / 'connectors' / 'leaky' / '.env.local').write_text(f'API_KEY={secret}\n', encoding='utf-8')
    client = harry.start()

    with client:
        response = client.get('/health')

    assert response.status_code == 200
    assert secret not in response.text
    assert '[redacted]' in response.text, 'the capability never got far enough to leak anything'


def test_no_capabilities_at_all_is_a_valid_start(harry):
    """A fresh install is not an error. It is also not silence — the counts say so."""
    with harry() as client:
        body = client.get('/health').json()

    assert body == {
        'status': 'ok',
        'roots': body['roots'],
        'loaded': 0,
        'skipped': 0,
        'capabilities': [],
        'jobs': {'scheduled': [], 'watched': []},
    }


def test_health_reports_where_it_looked(harry):
    """A capability missing from the list entirely is the baffling case: the folder is
    right there and nothing mentions it. Usually its root was never searched."""
    with harry('connectors/weather') as client:
        body = client.get('/health').json()

    assert any(root.endswith('.harry') for root in body['roots'])


# ---------------------------------------------------------------------------
# The other half of the answer: the log
# ---------------------------------------------------------------------------


def records_from_harry():
    """A handler on Harry's own logger, so what is captured is what that logger let
    through — not what pytest's root handler would have shown regardless."""
    captured: list[logging.LogRecord] = []

    class Collect(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            captured.append(record)

    handler = Collect()
    logging.getLogger('harry').addHandler(handler)
    return captured, handler


@pytest.mark.parametrize(('level', 'expect_start_up_lines'), [('INFO', True), ('WARNING', False)])
def test_harrys_own_log_level_follows_the_setting(harry, tmp_path, monkeypatch, level, expect_start_up_lines):
    """`HARRY_LOG_LEVEL` configured uvicorn and nothing of Harry's, so every line below
    WARNING went to logging's last-resort handler and vanished. The skip warnings still
    appeared, which is what made it look like the setting was applied."""
    (tmp_path / '.env').write_text(f'HARRY_LOG_LEVEL={level}\n', encoding='utf-8')
    harry.prepare('connectors/weather', 'connectors/broken')
    captured, handler = records_from_harry()

    try:
        client = harry.start()
        with client:
            client.get('/health')
    finally:
        logging.getLogger('harry').removeHandler(handler)

    said = [record.getMessage() for record in captured]
    assert any('skipped' in message for message in said), 'a skip must be visible at any level'
    assert any('weather loaded' in message for message in said) is expect_start_up_lines


def test_harry_gives_the_root_a_handler_when_nothing_else_has(monkeypatch, tmp_path):
    """The other half of the fix, and the half a test cannot see by accident. uvicorn
    configures its own three loggers and leaves the root alone, so without a handler
    there every line Harry logs goes to logging's last-resort one, which drops anything
    below WARNING.

    pytest installs its own root handler, so this removes them first — which is also why
    `basicConfig` is safe to call in the lifespan: it adds nothing when one is already
    there."""
    import harry.config

    (tmp_path / '.env').write_text('HARRY_LOG_LEVEL=INFO\n', encoding='utf-8')
    monkeypatch.chdir(tmp_path)
    harry.config.get_settings.cache_clear()

    root = logging.getLogger()
    existing = root.handlers[:]
    root.handlers.clear()
    try:
        configure_logging()
        assert root.handlers, 'nothing Harry logs below WARNING would reach stderr'
    finally:
        root.handlers[:] = existing
        harry.config.get_settings.cache_clear()


def test_health_says_what_the_clock_is_doing(harry, tmp_path):
    """ "The watchdog has been quiet — is it even watching?" is a real question at 07:10, and
    the answer has to be somewhere other than a log line from this morning."""
    with harry('jobs/ticker', 'jobs/morning-page') as client:
        jobs = client.get('/health').json()['jobs']

    assert [row['name'] for row in jobs['scheduled']] == ['ticker']
    assert jobs['scheduled'][0]['next_run'] is not None

    assert [row['name'] for row in jobs['watched']] == ['morning-page']
    assert jobs['watched'][0]['deadline'] == '07:00'
    assert jobs['watched'][0]['last_finished'] is None
