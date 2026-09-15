"""The first real capability in `.harry/`, tested the way Harry loads it.

Not imported — loaded. `pyproject.toml` deliberately keeps `.harry` off pytest's path so a
test cannot reach a connector directly and pass while the loader is broken. So these copy
the real folder into a temporary root, give it a credential, and load it.

Nothing here reaches Slack. The requests are recorded fixtures via respx, per
`.claude/rules/external-sources.md`.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import httpx
import pytest
import respx
from fastmcp import Client
from mcp.types import TextContent

from harry.alerts import Alerts
from harry.boundary import forbidden_imports
from harry.loader import load
from harry.mcp import FIND_TOOLS, build_server
from harry.store import Store

from .capability_copy import copy_capability

REPO = Path(__file__).parent.parent
POST_MESSAGE = 'https://slack.com/api/chat.postMessage'
TOKEN = 'xoxb-not-a-real-token-0123456789'


@pytest.fixture
def slack(tmp_path, monkeypatch):
    """The real `.harry/connectors/slack/`, loaded with a credential."""
    monkeypatch.delenv('HARRY_SLACK_BOT_TOKEN', raising=False)
    monkeypatch.delenv('HARRY_SLACK_CHANNEL', raising=False)

    def build(*, token: str = TOKEN, channel: str = '#harry'):
        root = tmp_path / 'root'
        folder = root / 'connectors' / 'slack'
        folder.parent.mkdir(parents=True, exist_ok=True)
        # dirs_exist_ok so one test may load the same tree twice, which is what a restart
        # looks like from here.
        copy_capability(REPO / '.harry' / 'connectors' / 'slack', folder)
        settings = ''.join(f'{key}={value}\n' for key, value in (('BOT_TOKEN', token), ('CHANNEL', channel)) if value)
        (folder / '.env.local').write_text(settings, encoding='utf-8')
        return load([root])

    return build


def connector(catalogue):
    found = catalogue.get('connector', 'slack')
    assert found is not None, [f'{c.name}: {c.reason}' for c in catalogue.skipped]
    return found


# ---------------------------------------------------------------------------
# The happy path
# ---------------------------------------------------------------------------


@respx.mock
def test_a_message_arrives_as_one_post_to_the_channel(slack):
    route = respx.post(POST_MESSAGE).mock(return_value=httpx.Response(200, json={'ok': True}))
    capability = connector(slack())

    capability.target.send('De Tijd login needs refreshing')

    assert route.call_count == 1
    request = route.calls[0].request
    assert request.headers['Authorization'] == f'Bearer {TOKEN}'
    sent = json.loads(request.read())
    assert sent == {'channel': '#harry', 'text': 'De Tijd login needs refreshing'}


@respx.mock
def test_the_connector_registers_itself_as_somewhere_alerts_go(slack):
    """A client and a sink from one folder — the role that does not use up the folder's one
    implementation."""
    route = respx.post(POST_MESSAGE).mock(return_value=httpx.Response(200, json={'ok': True}))
    capability = connector(slack())

    assert capability.alert_sink is not None
    Alerts.from_catalogue(slack()).send('something went wrong')

    assert route.call_count == 1


def test_the_call_carries_an_explicit_ceiling(slack, monkeypatch):
    """Alerts are sent while Harry is starting, and a socket that hangs with no ceiling
    holds up the restart somebody is watching.

    Asserted on the argument rather than on the resolved request, because httpx's own
    default is five seconds too — so a request with no `timeout=` at all produces
    byte-identical extensions, and a test reading those passes whether the connector chose
    anything or not.
    """
    passed: dict[str, object] = {}

    def spy(url, **kwargs):
        passed.update(kwargs)
        return httpx.Response(200, json={'ok': True}, request=httpx.Request('POST', url))

    monkeypatch.setattr(httpx, 'post', spy)
    connector(slack()).target.send('anything')

    assert passed['timeout'] == 5.0, 'the connector did not choose a ceiling of its own'


# ---------------------------------------------------------------------------
# Slack saying no
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ('code', 'why'),
    [
        ('invalid_auth', 'the token was revoked or rotated'),
        ('not_in_channel', 'the bot was never invited'),
        ('channel_not_found', 'the channel name is wrong'),
    ],
)
@respx.mock
def test_slacks_error_code_is_what_comes_back(slack, code, why):
    """The code is the part that tells you what to do, and the runbook beside the connector
    lists every one of these against its fix."""
    respx.post(POST_MESSAGE).mock(return_value=httpx.Response(200, json={'ok': False, 'error': code}))

    with pytest.raises(RuntimeError, match=code):
        connector(slack()).target.send('anything')


@respx.mock
def test_a_rejected_request_never_quotes_the_token_back(slack):
    """Slack echoes parts of a rejected request, and the request carried the bot token. The
    response body is exactly how a credential reaches a log line, so none of it is used."""
    respx.post(POST_MESSAGE).mock(
        return_value=httpx.Response(
            200,
            json={'ok': False, 'error': 'invalid_auth', 'echoed': {'token': TOKEN, 'headers': f'Bearer {TOKEN}'}},
        )
    )

    with pytest.raises(RuntimeError) as refused:
        connector(slack()).target.send('anything')

    assert TOKEN not in str(refused.value)


@respx.mock
def test_a_response_that_is_not_json_still_says_something_useful(slack):
    """A 502 from a proxy in front of Slack is HTML, not an API error."""
    respx.post(POST_MESSAGE).mock(return_value=httpx.Response(502, text='<html>Bad Gateway</html>'))

    with pytest.raises(RuntimeError, match='HTTP 502'):
        connector(slack()).target.send('anything')


@respx.mock
def test_slack_being_unreachable_costs_the_message_and_not_the_caller(slack, caplog):
    """Through Alerts, which is the way production reaches this: the connector raises, and
    whatever was reporting a problem carries on."""
    respx.post(POST_MESSAGE).mock(side_effect=httpx.ConnectError('no route to host'))
    alerts = Alerts.from_catalogue(slack())

    with caplog.at_level(logging.WARNING, logger='harry.alerts'):
        assert alerts.send('the tablet push failed twice') is False

    assert 'ConnectError' in caplog.text
    assert 'nobody was told: the tablet push failed twice' in caplog.text


@respx.mock
def test_a_call_that_times_out_is_handled_like_any_other_failure(slack, caplog):
    respx.post(POST_MESSAGE).mock(side_effect=httpx.ReadTimeout('slack did not answer'))
    alerts = Alerts.from_catalogue(slack())

    with caplog.at_level(logging.WARNING, logger='harry.alerts'):
        assert alerts.send('anything') is False

    assert 'ReadTimeout' in caplog.text


# ---------------------------------------------------------------------------
# Not configured
# ---------------------------------------------------------------------------


def test_without_a_token_the_connector_disables_itself_and_says_which_setting(slack):
    """A fresh checkout. Harry starts; there is simply nowhere for an alert to go."""
    catalogue = slack(token='')

    found = catalogue.get('connector', 'slack')
    assert found is not None and found.status == 'skipped'
    assert found.reason == 'required setting bot_token is not set'
    assert Alerts.from_catalogue(catalogue).send('nowhere to go') is True


def test_without_a_channel_it_says_that_one_instead(slack):
    catalogue = slack(channel='')

    found = catalogue.get('connector', 'slack')
    assert found is not None and found.reason == 'required setting channel is not set'


def test_the_committed_env_leaves_the_token_empty():
    """It is committed, generated, and read by every machine. A value there is a value in
    git."""
    committed = (REPO / '.harry' / 'connectors' / 'slack' / '.env').read_text(encoding='utf-8')

    assert 'BOT_TOKEN=\n' in committed
    assert 'CHANNEL=\n' in committed
    # The values, not the prose: the description above the key explains that a real token
    # starts `xoxb-`, which is documentation rather than a credential.
    values = [line.partition('=')[2] for line in committed.splitlines() if line and not line.startswith('#')]
    assert values == ['', '']


def test_the_real_capability_passes_the_gate():
    """The first folder under `.harry/` that is not a fixture. The declaration validates and
    its generated `.env` matches the schema — asserted here as well as in `make lint`, so a
    plain `make test` catches it too."""
    import check_capabilities
    import env_template

    assert check_capabilities.main([]) == 0
    assert env_template.main(['--check']) == 0


def test_two_missing_settings_read_as_a_sentence(slack):
    """This line reaches Slack and is read on a phone. "required settings bot_token,
    channel is not set" is not a sentence a person should be handed."""
    catalogue = slack(token='', channel='')

    found = catalogue.get('connector', 'slack')
    assert found is not None
    assert found.reason == 'required settings bot_token and channel are not set'


@pytest.mark.live
def test_a_message_really_arrives_in_a_real_workspace():
    """The only thing the recorded fixtures cannot prove: that a line lands in Slack.

    Everything above asserts what Harry sends and what it does with what comes back, which
    is the part that must never reach the network. This one needs a real token, a real
    channel and a bot that has actually been invited — and the invite is the step people
    skip, so it is the step worth a test that only passes when it was done.

    Run it deliberately: `make test-live ARGS=tests/test_slack_connector.py`. Then go and
    look at the channel.
    """
    catalogue = load()
    slack = catalogue.get('connector', 'slack')
    assert slack is not None, 'no slack connector on disk'
    assert slack.status == 'loaded', f'not configured: {slack.reason}'
    assert slack.alert_sink is not None

    slack.alert_sink('Harry says hello. This line came from make test-live.')


# ---------------------------------------------------------------------------
# Claude picks the channel
# ---------------------------------------------------------------------------


@respx.mock
def test_a_message_goes_where_the_caller_asked(slack):
    """The ask that started this: a failure to the alerting channel, a finished piece of
    work to the channel the people who asked for it are in."""
    route = respx.post(POST_MESSAGE).mock(return_value=httpx.Response(200, json={'ok': True}))
    client = connector(slack()).target

    where = client.send('the weekly reading list is ready', channel='#claude')

    assert where == '#claude'
    assert json.loads(route.calls[0].request.read())['channel'] == '#claude'


@respx.mock
def test_no_channel_means_the_configured_one(slack):
    """Which is what the alert path always does — deciding where a failure belongs is
    judgement, and Harry does not do judgement."""
    route = respx.post(POST_MESSAGE).mock(return_value=httpx.Response(200, json={'ok': True}))

    assert connector(slack()).target.send('something went wrong') == '#harry'
    assert json.loads(route.calls[0].request.read())['channel'] == '#harry'


@respx.mock
def test_an_alert_still_goes_to_the_configured_channel(slack):
    """Through Alerts, the way production raises one. Nothing to reconfigure."""
    route = respx.post(POST_MESSAGE).mock(return_value=httpx.Response(200, json={'ok': True}))

    Alerts.from_catalogue(slack()).send('the tablet push failed twice')

    assert json.loads(route.calls[0].request.read())['channel'] == '#harry'


@respx.mock
def test_a_channel_the_bot_is_not_in_says_how_to_fix_it(slack):
    """`chat:write` is not enough on its own, and inviting the bot is the step people skip.
    The code alone sends somebody to a search engine."""
    respx.post(POST_MESSAGE).mock(return_value=httpx.Response(200, json={'ok': False, 'error': 'not_in_channel'}))

    with pytest.raises(RuntimeError) as refused:
        connector(slack()).target.send('anything', channel='#finance')

    assert 'not_in_channel' in str(refused.value)
    assert '#finance' in str(refused.value)
    assert '/invite @Harry' in str(refused.value)


@respx.mock
def test_a_channel_that_does_not_exist_says_so_the_same_way(slack):
    respx.post(POST_MESSAGE).mock(return_value=httpx.Response(200, json={'ok': False, 'error': 'channel_not_found'}))

    with pytest.raises(RuntimeError) as refused:
        connector(slack()).target.send('anything', channel='#nowhere')

    assert '#nowhere' in str(refused.value)
    assert 'private channel' in str(refused.value)


@respx.mock
def test_a_code_with_no_advice_still_reports_the_code(slack):
    """The table has three entries, not every code Slack has. An unknown one is reported
    plainly rather than dressed up."""
    respx.post(POST_MESSAGE).mock(return_value=httpx.Response(200, json={'ok': False, 'error': 'ratelimited'}))

    with pytest.raises(RuntimeError, match='ratelimited'):
        connector(slack()).target.send('anything')


@respx.mock
def test_the_advice_never_repeats_the_token(slack):
    respx.post(POST_MESSAGE).mock(return_value=httpx.Response(200, json={'ok': False, 'error': 'invalid_auth'}))

    with pytest.raises(RuntimeError) as refused:
        connector(slack()).target.send('anything')

    assert TOKEN not in str(refused.value)
    assert 'Reinstall the Slack app' in str(refused.value)


# ---------------------------------------------------------------------------
# The tool, over MCP, the way Claude reaches it
# ---------------------------------------------------------------------------


@pytest.fixture
def harry_with_slack(tmp_path, monkeypatch):
    """The real connector *and* the real tool, loaded together and published."""
    import harry.config

    monkeypatch.delenv('HARRY_SLACK_BOT_TOKEN', raising=False)
    monkeypatch.delenv('HARRY_SLACK_CHANNEL', raising=False)
    settings = harry.config.Settings(data_dir=tmp_path / 'data')
    monkeypatch.setattr(harry.config, 'get_settings', lambda: settings)

    def build(*, token: str = TOKEN):
        root = tmp_path / 'root'
        for where in ('connectors/slack', 'tools/slack_post'):
            (root / where).parent.mkdir(parents=True, exist_ok=True)
            copy_capability(REPO / '.harry' / where, root / where)
        settings_file = root / 'connectors' / 'slack' / '.env.local'
        settings_file.write_text(f'BOT_TOKEN={token}\nCHANNEL=#harry\n' if token else 'CHANNEL=#harry\n', 'utf-8')
        return build_server(load([root]), Store(tmp_path / 'jobs.json'))

    return build


async def test_the_tool_is_deferred_and_found_by_searching(harry_with_slack):
    """Most tools defer. Posting a message is not something every session needs, and the
    roster is sent on every request."""
    server = harry_with_slack()

    async with Client(server) as connected:
        assert 'slack_post' not in [t.name for t in await connected.list_tools()]

        found = (await connected.call_tool(FIND_TOOLS, {'query': 'slack'})).data
        assert [row['name'] for row in found['found']] == ['slack_post']
        assert 'slack_post' in [t.name for t in await connected.list_tools()]


@respx.mock
async def test_claude_posts_to_a_named_channel(harry_with_slack):
    route = respx.post(POST_MESSAGE).mock(return_value=httpx.Response(200, json={'ok': True}))
    server = harry_with_slack()

    async with Client(server) as connected:
        await connected.call_tool(FIND_TOOLS, {'query': 'slack'})
        answer = (
            await connected.call_tool('slack_post', {'text': 'the reading list is ready', 'channel': '#claude'})
        ).data

    assert answer == {'channel': '#claude', 'posted': 'the reading list is ready'}
    assert json.loads(route.calls[0].request.read()) == {'channel': '#claude', 'text': 'the reading list is ready'}


@respx.mock
async def test_a_refusal_reaches_claude_as_an_error_with_the_fix_in_it(harry_with_slack):
    """Not a result with an error field in it — an error, so the model cannot mistake it
    for a message that went out."""
    respx.post(POST_MESSAGE).mock(return_value=httpx.Response(200, json={'ok': False, 'error': 'not_in_channel'}))
    server = harry_with_slack()

    async with Client(server) as connected:
        await connected.call_tool(FIND_TOOLS, {'query': 'slack'})
        result = await connected.call_tool('slack_post', {'text': 'x', 'channel': '#finance'}, raise_on_error=False)

    assert result.is_error
    said = ' '.join(block.text for block in result.content if isinstance(block, TextContent))
    assert '#finance' in said and '/invite @Harry' in said


async def test_without_a_credential_the_tool_is_not_offered_at_all(harry_with_slack):
    """Claude sees no tool rather than a tool that fails. A tool in the roster that cannot
    work is one the model picks, and the failure reads as a broken tool."""
    server = harry_with_slack(token='')

    async with Client(server) as connected:
        found = (await connected.call_tool(FIND_TOOLS, {'query': 'slack'})).data

    assert found['found'] == [], 'a tool whose connector has no credential was offered'


def test_the_tool_imports_the_sdk_and_nothing_else():
    """It reaches the connector through what it was handed, never by importing it. Two
    folders that import each other are two folders that cannot be swapped."""
    assert forbidden_imports(REPO / '.harry' / 'tools' / 'slack_post') == []


@respx.mock
async def test_leaving_the_channel_out_uses_the_configured_one(harry_with_slack):
    """Asserted through the tool, not through the connector beneath it. The roster could
    start demanding a channel and a test one layer down would never say so."""
    route = respx.post(POST_MESSAGE).mock(return_value=httpx.Response(200, json={'ok': True}))
    server = harry_with_slack()

    async with Client(server) as connected:
        await connected.call_tool(FIND_TOOLS, {'query': 'slack'})
        answer = (await connected.call_tool('slack_post', {'text': 'no channel given'})).data

    assert answer == {'channel': '#harry', 'posted': 'no channel given'}
    assert json.loads(route.calls[0].request.read())['channel'] == '#harry'


async def test_the_tools_annotations_reach_the_client(harry_with_slack):
    """The first tool here that is not read-only. Its annotations are what let a client gate
    a thing that posts into a shared workspace without gating one that reads a feed."""
    server = harry_with_slack()

    async with Client(server) as connected:
        await connected.call_tool(FIND_TOOLS, {'query': 'slack'})
        published = {t.name: t for t in await connected.list_tools()}['slack_post']

    assert published.annotations is not None
    assert published.annotations.read_only_hint is False
    assert published.annotations.destructive_hint is False
    assert published.annotations.idempotent_hint is False
    assert published.annotations.open_world_hint is True
