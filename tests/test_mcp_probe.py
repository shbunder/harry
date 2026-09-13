# pyright: reportPrivateUsage=false
#
# `_call` and `_is_unreachable` are private and are exactly what needs testing: the
# first is the path that reports PASS, the second decides UNKNOWN against FAIL, and
# both shipped wrong once already.
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
    monkeypatch.setattr(mcp_probe, 'LOG_PATH', path)
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


def test_a_log_it_cannot_write_says_so_rather_than_failing_silently(monkeypatch, tmp_path, capsys):
    """Best effort, but never silent.

    If this swallowed the error, `calls` would afterwards report "nothing has called the
    probe" for a probe that was reached every time — and the false negative is
    indistinguishable from the real one, which is the whole question `calls` answers.
    """
    monkeypatch.setattr(mcp_probe, 'LOG_PATH', tmp_path / 'nope' / 'calls.jsonl')
    monkeypatch.setattr(mcp_probe.Path, 'mkdir', lambda *a, **k: (_ for _ in ()).throw(OSError('read-only')))

    assert 'pong from' in mcp_probe.ping()
    assert 'could not write the call log' in capsys.readouterr().err


# ---------------------------------------------------------------------------
# The server, in process
# ---------------------------------------------------------------------------


async def test_a_client_reaches_every_tool_and_gets_an_answer(probe_log):
    server = mcp_probe.build_server(bearer='test-token')
    async with Client(server) as client:
        assert sorted(tool.name for tool in await client.list_tools()) == [
            'ping',
            'sleep',
            'sleep_reporting',
        ]

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
    assert 'pass --ping, --sleep SECONDS or --sleep-reporting' in capsys.readouterr().err


def test_serve_is_wired_to_the_transport_it_says(probe_log, monkeypatch):
    seen: dict = {}
    monkeypatch.setattr(mcp_probe.FastMCP, 'run', lambda self, **kw: seen.update(kw))

    assert mcp_probe.main(['serve', '--port', '7499', '--host', '0.0.0.0']) == 0
    assert seen == {'transport': 'http', 'host': '0.0.0.0', 'port': 7499}

    seen.clear()
    assert mcp_probe.main(['serve', '--stdio']) == 0
    assert seen == {'transport': 'stdio'}


def test_the_token_and_port_come_from_harrys_own_settings(monkeypatch):
    """Through config.py, never os.environ.

    This is not style. `os.environ` does not read `.env.local`, so the earlier version
    returned the hardcoded default on a machine with a real token configured — and read
    port 7430 inside a worktree whose `.env.local` says 7431, binding the primary
    checkout's port. That is the collision `make worktree` exists to prevent.
    """
    from pydantic import SecretStr

    from harry.config import Settings

    def fake(port: int, token: str):
        settings = Settings(port=port, api_token=SecretStr(token))
        monkeypatch.setattr(mcp_probe, 'get_settings', lambda: settings)

    fake(7431, 'from-dot-env-local')
    assert mcp_probe.port() == 7431
    assert mcp_probe.token() == 'from-dot-env-local'

    fake(7430, '')
    assert mcp_probe.token() == mcp_probe.DEFAULT_TOKEN, 'an unset token falls back, it does not blow up'


def test_the_probe_and_harry_never_disagree_about_the_port(monkeypatch):
    """One owner. Asserted by asking both and comparing, not by reading the code."""
    from harry.config import Settings

    monkeypatch.setattr(mcp_probe, 'get_settings', lambda: Settings(port=7499))
    assert mcp_probe.port() == Settings(port=7499).port == 7499


async def test_a_wrong_token_does_not_reach_the_tools(probe_log):
    """The probe goes behind a tunnel, which is exactly where an unprotected one is a
    problem. Asserted against the server rather than assumed from the config."""
    server = mcp_probe.build_server(bearer='the-right-one')
    verifier = server.auth
    assert verifier is not None, 'the probe goes behind a tunnel; it must not be unauthenticated'
    assert await verifier.verify_token('the-right-one') is not None
    assert await verifier.verify_token('the-wrong-one') is None


async def test_a_server_that_is_not_there_reports_unknown_not_fail(probe_log, capsys):
    """The half that decides what a run means.

    A refused connection and a call that gave up at a length are different answers, and
    the probe has to say which — otherwise "the tunnel was down" gets written up as
    "blocking calls do not work", which would have rewritten a design.

    Port 1 is reserved and nothing listens on it, so this refuses immediately rather
    than reaching the network.
    """
    assert await mcp_probe._call('http://127.0.0.1:1/mcp', 'token', None, timeout=5.0) == 1
    err = capsys.readouterr().err
    assert err.startswith('UNKNOWN'), f'a refused connection is not a finding: {err}'
    assert 'Not a finding' in err


def test_a_refused_connection_is_recognised_through_its_cause_chain():
    """The outer exception is a RuntimeError; the real cause is chained underneath, so
    an isinstance check on the outer one reported a refusal as FAIL."""
    refused = RuntimeError('Client failed to connect: All connection attempts failed')
    refused.__cause__ = ConnectionError('nope')
    assert mcp_probe._is_unreachable(refused)

    assert mcp_probe._is_unreachable(TimeoutError('slow'))
    assert not mcp_probe._is_unreachable(ValueError('the tool raised'))


def test_the_pass_path_runs_end_to_end_through_the_command_line(probe_log, monkeypatch, capsys):
    """The thing this script exists to do had no test: connect, list, call, print PASS.

    Driven through `main()` against a real in-process server, so it goes the way somebody
    typing `make probe ARGS="call --ping"` goes rather than round the side. Synchronous
    on purpose: `main()` owns the event loop, and an async test would already be in one.
    """
    server = mcp_probe.build_server(bearer='test-token')

    async def in_process(url, bearer, seconds, timeout, reporting=None, every=30):
        async with Client(server) as client:
            result = await client.call_tool('ping', {})
            print(f'PASS — ping returned: {result.data}')
            return 0

    monkeypatch.setattr(mcp_probe, '_call', in_process)
    assert mcp_probe.main(['call', '--ping']) == 0
    assert 'PASS' in capsys.readouterr().out


def test_sleep_reporting_is_reachable_from_the_command_line(probe_log, monkeypatch):
    """It shipped as a flag that did nothing: `cmd_call` never read `args.reporting`, so
    the finding this feature exists to reproduce could not be reproduced through the
    interface built to reproduce it."""
    seen: dict = {}

    async def capture(url, bearer, seconds, timeout, reporting=None, every=30):
        seen.update(reporting=reporting, every=every, seconds=seconds)
        return 0

    monkeypatch.setattr(mcp_probe, '_call', capture)
    assert mcp_probe.main(['call', '--sleep-reporting', '660', '--every', '30']) == 0
    assert seen == {'reporting': 660, 'every': 30, 'seconds': None}


async def test_sleep_reporting_emits_progress_while_it_blocks(probe_log):
    """The lever that may defeat a client's idle ceiling.

    A client aborts a tool that has sent no response *or progress* for some period —
    Claude Code's default is 300s. A long job that reports progress should reset that
    timer on every notification, which matters because a server cannot configure its
    clients. Asserting the notifications arrive is the server half of that; whether a
    given client honours them is that client's half.
    """
    seen: list[str] = []

    async def on_progress(progress: float, total: float | None, message: str | None) -> None:
        seen.append(f'{progress:.0f}/{total:.0f} {message}')

    server = mcp_probe.build_server(bearer='test-token')
    async with Client(server, progress_handler=on_progress) as client:
        result = await client.call_tool('sleep_reporting', {'seconds': 3, 'every': 1})

    assert 'still returned' in str(result.data)
    assert len(seen) == 3, f'expected one notification per second, got {seen}'
    assert seen[0].startswith('1/3')
    assert seen[-1].startswith('3/3')


async def test_sleep_reporting_still_works_with_no_progress_handler(probe_log):
    """A caller that ignores progress must not break the call."""
    server = mcp_probe.build_server(bearer='test-token')
    async with Client(server) as client:
        result = await client.call_tool('sleep_reporting', {'seconds': 1, 'every': 1})
    assert 'still returned' in str(result.data)
