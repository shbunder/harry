"""What loaded, what did not, and why — over HTTP, the way anything would ask.

Every test here starts the real app and lets its start-up run, because the question is
what somebody gets when they call `/health` on a Harry that has just come up. Calling the
catalogue directly would answer a question nobody asks.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from harry.main import build_app

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

    def build(*capabilities: str) -> TestClient:
        root_with(tmp_path / '.harry', *capabilities)
        return TestClient(build_app())

    yield build
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

    client = harry('connectors/leaky', 'connectors/weather')
    (tmp_path / '.harry' / 'connectors' / 'leaky' / '.env.local').write_text(f'API_KEY={secret}\n', encoding='utf-8')

    with client:
        response = client.get('/health')

    assert response.status_code == 200
    assert secret not in response.text
    assert '[redacted]' in response.text, 'the capability never got far enough to leak anything'


def test_no_capabilities_at_all_is_a_valid_start(harry):
    """A fresh install is not an error. It is also not silence — the counts say so."""
    with harry() as client:
        body = client.get('/health').json()

    assert body == {'status': 'ok', 'roots': body['roots'], 'loaded': 0, 'skipped': 0, 'capabilities': []}


def test_health_reports_where_it_looked(harry):
    """A capability missing from the list entirely is the baffling case: the folder is
    right there and nothing mentions it. Usually its root was never searched."""
    with harry('connectors/weather') as client:
        body = client.get('/health').json()

    assert any(root.endswith('.harry') for root in body['roots'])
