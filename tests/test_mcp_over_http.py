"""The door, over a real socket.

FastMCP's in-memory transport carries no HTTP headers, so it cannot carry a bearer token —
which means the one thing standing between Harry and anybody who can reach the port is the
one thing `tests/test_mcp.py` cannot check. These tests start Harry on a real port and knock
on it.

Localhost only. Nothing here reaches the network, so it belongs in the gate rather than
behind `make test-live`.
"""

from __future__ import annotations

import threading
import time

import pytest
import uvicorn
from fastmcp import Client
from fastmcp.client.auth import BearerAuth
from pydantic import SecretStr

from harry.main import build_app

from .test_loader import root_with

TOKEN = 'a-token-for-the-tests-only'


def bearer(token: str) -> BearerAuth:
    """`auth=<string>` starts an OAuth flow rather than sending a bearer header.

    That distinction cost a debugging round: the right token came back 401 because it
    was never sent as one."""
    return BearerAuth(token)


@pytest.fixture
def serving(tmp_path, monkeypatch):
    """A Harry on a real port, with a known token, torn down after the test."""
    import harry.config

    monkeypatch.delenv('HARRY_ICLOUD_APP_PASSWORD', raising=False)
    settings = harry.config.Settings(api_token=SecretStr(TOKEN), data_dir=tmp_path / 'data', log_level='WARNING')
    monkeypatch.setattr(harry.config, 'get_settings', lambda: settings)
    monkeypatch.setattr(harry.config, 'BUNDLED_CAPABILITIES', tmp_path / 'no-bundled')

    started: list[uvicorn.Server] = []

    def start(*capabilities: str) -> str:
        root_with(tmp_path / '.harry', *capabilities)
        monkeypatch.chdir(tmp_path)

        # Port 0 lets the kernel pick, so two of these can never collide — including with
        # whatever Harry this worktree already has running on 7431.
        server = uvicorn.Server(uvicorn.Config(build_app(), host='127.0.0.1', port=0, log_level='error'))
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        started.append(server)

        deadline = time.monotonic() + 10
        while not server.started and time.monotonic() < deadline:
            time.sleep(0.02)
        assert server.started, 'Harry did not come up'
        return f'http://127.0.0.1:{server.servers[0].sockets[0].getsockname()[1]}/mcp'

    yield start

    for server in started:
        server.should_exit = True
    time.sleep(0.2)


async def test_a_client_with_the_configured_token_gets_the_roster(serving):
    """The end-to-end claim the whole feature rests on: a client somewhere else, over HTTP,
    with a token, reaching a tool a capability declared."""
    url = serving('connectors/weather', 'tools/weather_forecast')

    async with Client(url, auth=bearer(TOKEN)) as connected:
        names = [tool.name for tool in await connected.list_tools()]
        result = await connected.call_tool('weather_forecast', {'day': 'today'})

    assert 'weather_forecast' in names
    assert result.data == {'day': 'today', 'summary': 'grey, as ever'}


async def test_a_client_with_no_token_is_refused(serving):
    url = serving('connectors/weather', 'tools/weather_forecast')

    with pytest.raises(Exception) as refused:
        async with Client(url) as connected:
            await connected.list_tools()

    assert 'weather_forecast' not in str(refused.value)


async def test_a_client_with_the_wrong_token_is_refused(serving):
    """A wrong token is not a quieter version of the right one."""
    url = serving('connectors/weather', 'tools/weather_forecast')

    with pytest.raises(Exception) as refused:
        async with Client(url, auth=bearer('not-the-configured-one')) as connected:
            await connected.list_tools()

    assert 'weather_forecast' not in str(refused.value)


async def test_an_unconfigured_harry_authorises_nobody(tmp_path, monkeypatch):
    """The dangerous default. An empty configured token must never mean "anything
    matches" — that is how an unconfigured Harry behind a tunnel serves the internet."""
    import harry.config

    settings = harry.config.Settings(api_token=SecretStr(''), data_dir=tmp_path / 'data', log_level='WARNING')
    monkeypatch.setattr(harry.config, 'get_settings', lambda: settings)
    monkeypatch.setattr(harry.config, 'BUNDLED_CAPABILITIES', tmp_path / 'no-bundled')
    root_with(tmp_path / '.harry', 'connectors/weather', 'tools/weather_forecast')
    monkeypatch.chdir(tmp_path)

    server = uvicorn.Server(uvicorn.Config(build_app(), host='127.0.0.1', port=0, log_level='error'))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.02)
    url = f'http://127.0.0.1:{server.servers[0].sockets[0].getsockname()[1]}/mcp'

    try:
        with pytest.raises(Exception):
            async with Client(url, auth=bearer('')) as connected:
                await connected.list_tools()
        with pytest.raises(Exception):
            async with Client(url, auth=bearer('anything-at-all')) as connected:
                await connected.list_tools()
    finally:
        server.should_exit = True
        time.sleep(0.2)


async def test_a_tool_that_asks_who_is_calling_is_handed_the_caller(serving):
    """Filled in by Harry from the token, never by the caller. A principal the caller could
    pass would be a caller claiming to be somebody, which is worth nothing."""
    url = serving('tools/account_whoami')

    async with Client(url, auth=bearer(TOKEN)) as connected:
        published = {tool.name: tool for tool in await connected.list_tools()}['account_whoami']
        result = await connected.call_tool('account_whoami', {})

    assert result.data == {'id': 'owner', 'name': 'the owner'}
    assert 'principal' not in published.input_schema.get('properties', {})
    assert published.input_schema.get('required', []) == []


async def test_health_is_served_alongside_the_mcp_endpoint(serving):
    """Both on one app. /health is how you find out a capability was skipped; /mcp is how
    Claude reaches the ones that were not."""
    import httpx

    url = serving('connectors/icloud', 'connectors/weather', 'tools/weather_forecast')
    base = url.removesuffix('/mcp')

    async with httpx.AsyncClient() as http:
        health = (await http.get(f'{base}/health')).json()

    skipped = {row['name']: row for row in health['capabilities'] if row['status'] == 'skipped'}
    assert skipped['icloud']['reason'] == 'required setting app_password is not set'
    assert health['loaded'] == 2


async def test_an_async_tool_is_handed_the_caller_too(serving):
    """Every tool that fetches anything over the network will be async, so that is the
    branch production mostly takes — and it was the one with no test."""
    url = serving('tools/account_describe')

    async with Client(url, auth=bearer(TOKEN)) as connected:
        published = {tool.name: tool for tool in await connected.list_tools()}['account_describe']
        result = await connected.call_tool('account_describe', {})

    assert result.data == {'id': 'owner', 'name': 'the owner', 'awaited': True}
    assert 'principal' not in published.input_schema.get('properties', {})
