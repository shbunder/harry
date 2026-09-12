"""The MCP probe.

It is the thing that answers "can this client reach Harry", so the failure that matters
is it answering wrongly — a UNKNOWN that should have been a PASS, or a call that was
never recorded. Both are tested here.

The server half runs in process: FastMCP's client connects to a server object directly,
so reachability is provable without a port or a tunnel.
"""

from __future__ import annotations

import datetime as dt
import json

import pytest
from fastmcp import Client

import mcp_probe


@pytest.fixture(autouse=True)
def probe_log(tmp_path, monkeypatch):
    """Point the call log somewhere throwaway. Every test gets a clean one."""
    path = tmp_path / 'calls.jsonl'
    monkeypatch.setenv('HARRY_PROBE_LOG', str(path))
    return path


# ---------------------------------------------------------------------------
# The tools
# ---------------------------------------------------------------------------


def test_ping_answers_and_is_recorded(probe_log):
    answer = mcp_probe.ping()
    assert 'pong from' in answer

    entries = [json.loads(line) for line in probe_log.read_text().splitlines()]
    assert [e['tool'] for e in entries] == ['ping']
    assert entries[0]['detail'] == answer


def test_sleep_records_both_ends(probe_log):
    """Two entries, not one: a call that started and never finished is the interesting
    case, and one entry at the end cannot show it."""
    answer = mcp_probe.sleep(0)
    assert 'still returned' in answer

    entries = [json.loads(line) for line in probe_log.read_text().splitlines()]
    assert [e['tool'] for e in entries] == ['sleep', 'sleep']
    assert 'started' in entries[0]['detail']
    assert 'still returned' in entries[1]['detail']


def test_a_log_it_cannot_write_does_not_break_the_probe(monkeypatch, tmp_path):
    """Best effort by design — a probe that cannot write its log still answers."""
    monkeypatch.setenv('HARRY_PROBE_LOG', str(tmp_path / 'nope' / 'calls.jsonl'))
    monkeypatch.setattr(mcp_probe.Path, 'mkdir', lambda *a, **k: (_ for _ in ()).throw(OSError('read-only')))
    assert 'pong from' in mcp_probe.ping()


# ---------------------------------------------------------------------------
# The server, in process
# ---------------------------------------------------------------------------


async def test_a_client_reaches_both_tools_and_gets_an_answer(probe_log):
    server = mcp_probe.build_server(bearer='test-token')
    async with Client(server) as client:
        assert sorted(tool.name for tool in await client.list_tools()) == ['ping', 'sleep']

        result = await client.call_tool('ping', {})
        assert 'pong from' in str(result.data)

        result = await client.call_tool('sleep', {'seconds': 0})
        assert 'still returned' in str(result.data)

    assert len(probe_log.read_text().splitlines()) == 3


async def test_the_tools_carry_a_description_a_caller_can_choose_from(probe_log):
    """The docstring is what a model reads to decide whether to call it, so an empty one
    is a tool that can only be picked by name."""
    server = mcp_probe.build_server(bearer='test-token')
    async with Client(server) as client:
        described = {tool.name: (tool.description or '') for tool in await client.list_tools()}
    assert 'reach Harry at all' in described['ping']
    assert 'gives up first' in described['sleep']


# ---------------------------------------------------------------------------
# Reading the log back
# ---------------------------------------------------------------------------


def write_calls(path, *entries):
    path.write_text('\n'.join(json.dumps(e) for e in entries) + '\n', encoding='utf-8')


def test_calls_reports_nothing_as_unknown_not_as_failure(probe_log, capsys):
    """Nothing having called is not evidence that nothing can."""
    assert mcp_probe.main(['calls']) == 1
    err = capsys.readouterr().err
    assert 'UNKNOWN' in err
    assert 'not' in err and 'finding' in err


def test_calls_lists_what_arrived(probe_log, capsys):
    now = dt.datetime.now().isoformat(timespec='seconds')
    write_calls(probe_log, {'at': now, 'tool': 'ping', 'detail': 'pong from nuc'})
    assert mcp_probe.main(['calls']) == 0
    out = capsys.readouterr().out
    assert 'pong from nuc' in out
    assert 'PASS' in out


def test_calls_outside_the_window_are_not_counted(probe_log, capsys):
    old = (dt.datetime.now() - dt.timedelta(hours=48)).isoformat(timespec='seconds')
    write_calls(probe_log, {'at': old, 'tool': 'ping', 'detail': 'ancient'})
    assert mcp_probe.main(['calls', '--since', '24']) == 1
    assert mcp_probe.main(['calls', '--since', '72']) == 0
    assert 'ancient' in capsys.readouterr().out


def test_a_corrupt_line_is_skipped_rather_than_fatal(probe_log, capsys):
    now = dt.datetime.now().isoformat(timespec='seconds')
    probe_log.write_text(
        'not json\n'
        + json.dumps({'at': 'not a date', 'tool': 'ping', 'detail': 'x'})
        + '\n'
        + json.dumps({'at': now, 'tool': 'ping', 'detail': 'the good one'})
        + '\n',
        encoding='utf-8',
    )
    assert mcp_probe.main(['calls']) == 0
    assert 'the good one' in capsys.readouterr().out


# ---------------------------------------------------------------------------
# The command line
# ---------------------------------------------------------------------------


def test_call_needs_to_be_told_what_to_do(probe_log, capsys):
    with pytest.raises(SystemExit):
        mcp_probe.main(['call'])
    assert 'pass --ping or --sleep' in capsys.readouterr().err


def test_serve_is_wired_to_the_transport_it_says(probe_log, monkeypatch):
    seen: dict = {}
    monkeypatch.setattr(mcp_probe.FastMCP, 'run', lambda self, **kw: seen.update(kw))

    assert mcp_probe.main(['serve', '--port', '7499', '--host', '0.0.0.0']) == 0
    assert seen == {'transport': 'http', 'host': '0.0.0.0', 'port': 7499}

    seen.clear()
    assert mcp_probe.main(['serve', '--stdio']) == 0
    assert seen == {'transport': 'stdio'}


def test_the_bearer_token_comes_from_the_environment(monkeypatch):
    monkeypatch.delenv('HARRY_API_TOKEN', raising=False)
    assert mcp_probe.token() == mcp_probe.DEFAULT_TOKEN
    monkeypatch.setenv('HARRY_API_TOKEN', 'from-the-env')
    assert mcp_probe.token() == 'from-the-env'


async def test_a_wrong_token_does_not_reach_the_tools(probe_log):
    """The probe goes behind a tunnel, which is exactly where an unprotected one is a
    problem. Asserted against the server rather than assumed from the config."""
    server = mcp_probe.build_server(bearer='the-right-one')
    verifier = server.auth
    assert verifier is not None, 'the probe goes behind a tunnel; it must not be unauthenticated'
    assert await verifier.verify_token('the-right-one') is not None
    assert await verifier.verify_token('the-wrong-one') is None


async def test_a_server_that_is_not_there_reports_unknown_not_a_finding(probe_log, capsys):
    """The half that decides what a run means. A refused connection and a call that
    timed out at a specific length are different answers, and the probe has to say which
    — otherwise "the tunnel is down" gets written up as "blocking calls do not work"."""
    # Port 1 is reserved and nothing listens on it, so this refuses immediately.
    assert await mcp_probe._call('http://127.0.0.1:1/mcp', 'token', None, timeout=5.0) == 1
    err = capsys.readouterr().err
    assert err.startswith('FAIL')
    assert 'UNKNOWN, not a finding' in err
