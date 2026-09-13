"""The first real capability in `.harry/`, tested the way Harry loads it.

Not imported — loaded. `pyproject.toml` deliberately keeps `.harry` off pytest's path so a
test cannot reach a connector directly and pass while the loader is broken. So these copy
the real folder into a temporary root, give it a credential, and load it.

Nothing here reaches Slack. The requests are recorded fixtures via respx, per
`.claude/rules/external-sources.md`.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

import httpx
import pytest
import respx

from harry.alerts import Alerts
from harry.loader import load

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
        shutil.copytree(REPO / '.harry' / 'connectors' / 'slack', folder, dirs_exist_ok=True)
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
    import json

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


@respx.mock
def test_the_call_carries_a_five_second_ceiling(slack):
    """Alerts are sent while Harry is starting, and a socket that hangs with no ceiling
    holds up the restart somebody is watching."""
    route = respx.post(POST_MESSAGE).mock(return_value=httpx.Response(200, json={'ok': True}))
    connector(slack()).target.send('anything')

    timeout = route.calls[0].request.extensions['timeout']
    assert timeout['connect'] == 5.0
    assert timeout['read'] == 5.0


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
