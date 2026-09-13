#!/usr/bin/env python3
"""A minimal MCP server, and a client for it, to answer "can X reach Harry?".

Two tools and nothing else:

  ping()            returns immediately, so reachability is answerable on its own
  sleep()           blocks silently, so a client's idle ceiling is answerable on its own
  sleep_reporting() blocks while reporting progress, which is the lever that may defeat it

Answering both against the same server is the point — two slightly different servers
would let a failure hide in the difference between them.

Every call is appended to a log, so a question like "did the scheduled task actually
reach us at 06:30" has an answer afterwards instead of needing somebody to be watching.

    make probe                                  # serve on HARRY_PORT
    make probe ARGS="call --ping"               # reach it
    make probe ARGS="call --sleep 300"          # hold a call open for five minutes
    make probe ARGS="call --ping --url https://harry.example.com/mcp"
    make probe ARGS="calls"                     # what has called us, and when

This began as a Phase 0 spike and was kept because it answers the same question every
time the tunnel, the client or the host changes.
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from fastmcp import Client, Context, FastMCP

# Not `providers.bearer`, which is where you look first and where it is not.
from fastmcp.server.auth.providers.jwt import StaticTokenVerifier

from harry.config import get_settings

SUMMARY = (__doc__ or '').partition('\n')[0]

DEFAULT_TOKEN = 'probe-token-not-a-secret'

# A plain constant, not a setting. It is where this script keeps its own notes; Harry
# never reads it, so putting it in `config.py` would add a key nobody configures.
LOG_PATH = Path.home() / '.harry-probe' / 'calls.jsonl'


def token() -> str:
    """The bearer token, from Harry's own settings.

    Through `config.py`, never `os.environ` — that is the rule in
    `.claude/rules/secrets-and-config.md`, and it is not theoretical here. `os.environ`
    does not read `.env.local`, so a machine with a real token configured would have got
    the hardcoded default below and never known.
    """
    return get_settings().api_token.get_secret_value() or DEFAULT_TOKEN


def port() -> int:
    """Harry's port, from the one place that owns it.

    Reading `HARRY_PORT` from the environment instead gave 7430 inside a worktree whose
    `.env.local` says 7431 — binding the primary checkout's port, which is the exact
    collision `make worktree` exists to prevent.
    """
    return get_settings().port


def log_path() -> Path:
    return LOG_PATH


def record(tool: str, detail: str) -> None:
    """Append one call. Best effort: a probe that cannot write its log still answers."""
    path = log_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        entry = {'at': dt.datetime.now().isoformat(timespec='seconds'), 'tool': tool, 'detail': detail}
        with path.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(entry) + '\n')
    except OSError as error:
        # Never silently: `calls` would then report "nothing has called the probe" for a
        # probe that was reached every time, and the two look identical from outside.
        print(f'warning: could not write the call log at {path}: {error}', file=sys.stderr)


def read_calls(since_hours: int) -> list[dict[str, Any]]:
    """Every logged call inside the window, oldest first. A bad line is skipped."""
    path = log_path()
    if not path.exists():
        return []
    cutoff = dt.datetime.now() - dt.timedelta(hours=since_hours)
    found: list[dict[str, Any]] = []
    for line in path.read_text(encoding='utf-8').splitlines():
        try:
            entry = json.loads(line)
            if dt.datetime.fromisoformat(entry['at']) >= cutoff:
                found.append(entry)
        except (ValueError, KeyError, TypeError):
            continue
    return found


# ---------------------------------------------------------------------------
# The two tools
# ---------------------------------------------------------------------------


def ping() -> str:
    """Return immediately, naming the host and its local time.

    Call this to confirm you can reach Harry at all. It touches nothing and takes no
    arguments.
    """
    answer = f'pong from {os.uname().nodename} at {time.strftime("%Y-%m-%d %H:%M:%S %Z")}'
    record('ping', answer)
    return answer


def sleep(seconds: int = 300) -> str:
    """Block for `seconds`, then report how long it actually took.

    This exists to find out whether a call held open that long returns its result, or
    whether something between here and the caller gives up first.
    """
    started = time.time()
    record('sleep', f'started, asked for {seconds}s')
    time.sleep(seconds)
    waited = time.time() - started
    answer = f'slept {waited:.1f}s (asked for {seconds}s) and still returned'
    record('sleep', answer)
    return answer


# 30s against Claude Code's 300s idle default — a tenfold margin, and no client has to
# configure anything to get it.
DEFAULT_PROGRESS_INTERVAL = 30


async def sleep_reporting(
    seconds: int = 600, every: int = DEFAULT_PROGRESS_INTERVAL, context: Context | None = None
) -> str:
    """Block for `seconds`, sending a progress notification every `every` seconds.

    The same question as `sleep`, with the one lever that might defeat the client's
    ceiling. A client aborts a tool that has sent no response *or progress* for some
    period, so a long job that reports progress may hold open indefinitely — without the
    caller having to configure anything, which matters because a server cannot configure
    its clients.
    """
    started = time.time()
    record('sleep_reporting', f'started, asked for {seconds}s reporting every {every}s')
    elapsed = 0
    while elapsed < seconds:
        await asyncio.sleep(min(every, seconds - elapsed))
        elapsed = int(time.time() - started)
        if context is not None:
            await context.report_progress(elapsed, seconds, f'{elapsed}s of {seconds}s')
    waited = time.time() - started
    answer = f'slept {waited:.1f}s while reporting progress every {every}s, and still returned'
    record('sleep_reporting', answer)
    return answer


def build_server(bearer: str | None = None) -> FastMCP:
    """A server carrying both tools, behind a bearer token.

    Auth from the first line: the moment this is put behind a tunnel it is reachable
    from the internet, and a probe is exactly the thing somebody forgets to protect.
    """
    secret = bearer or token()
    return FastMCP(
        name='harry-probe',
        instructions='A probe. Two tools: ping, and a sleep that blocks.',
        auth=StaticTokenVerifier(tokens={secret: {'client_id': 'probe', 'scopes': []}}),
        tools=[ping, sleep, sleep_reporting],
    )


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def cmd_serve(args: argparse.Namespace) -> int:
    server = build_server()
    if args.stdio:
        server.run(transport='stdio')
        return 0
    print(f'listening on http://{args.host}:{args.port}/mcp', file=sys.stderr)
    print(f'bearer token: {token()}', file=sys.stderr)
    print(f'calls logged to: {log_path()}', file=sys.stderr)
    server.run(transport='http', host=args.host, port=args.port)
    return 0


def _is_unreachable(error: BaseException) -> bool:
    """Whether this is "the server was not there" rather than "it gave up on us".

    The type alone is not enough: a refused connection arrives as a RuntimeError with the
    real cause chained underneath, so checking isinstance on the outer exception reported
    a connection refusal as FAIL — the exact confusion the three exit states exist to
    prevent. Walk the chain, and fall back to the message.
    """
    seen: BaseException | None = error
    while seen is not None:
        if isinstance(seen, (ConnectionError, OSError, TimeoutError)):
            return True
        seen = seen.__cause__ or seen.__context__
    return 'connect' in str(error).lower()


async def _call(
    url: str,
    bearer: str,
    seconds: int | None,
    timeout: float,
    reporting: int | None = None,
    every: int = 30,
) -> int:
    started = time.time()
    try:
        # `auth=<str>` is the bearer shorthand — the raw token, not "Bearer <token>".
        async with Client(url, auth=bearer, timeout=timeout) as client:
            names = sorted(tool.name for tool in await client.list_tools())
            print(f'connected — tools: {", ".join(names)}')

            started = time.time()
            if reporting is not None:
                print(f'calling sleep_reporting({reporting}, every={every})…', flush=True)
                result = await client.call_tool('sleep_reporting', {'seconds': reporting, 'every': every})
                took = time.time() - started
                print(f'PASS — a {reporting}s call reporting every {every}s returned after {took:.1f}s')
                print(f'       server said: {result.data}')
                return 0

            if seconds is None:
                result = await client.call_tool('ping', {})
                print(f'PASS — ping returned in {time.time() - started:.2f}s: {result.data}')
                return 0

            print(f'calling sleep({seconds})… holding the call open', flush=True)
            result = await client.call_tool('sleep', {'seconds': seconds})
            took = time.time() - started
            print(f'PASS — a {seconds}s blocking call returned after {took:.1f}s')
            print(f'       server said: {result.data}')
            print(f'       client timeout was {timeout}s')
            return 0
    except Exception as error:
        took = time.time() - started
        # The requirements page makes this distinction load-bearing: a spike that could
        # not reach its service has not run, and reporting that as FAIL is how "the
        # tunnel was down" gets written up as "blocking calls do not work".
        unreachable = _is_unreachable(error)
        if unreachable:
            print(f'UNKNOWN — could not reach it: {type(error).__name__} after {took:.1f}s: {error}', file=sys.stderr)
            print('          Not a finding. The server may simply not be up.', file=sys.stderr)
        else:
            print(f'FAIL — {type(error).__name__} after {took:.1f}s: {error}', file=sys.stderr)
            print(f'       It was reached and then gave up at {took:.0f}s, which is a finding.', file=sys.stderr)
        return 1


def cmd_call(args: argparse.Namespace) -> int:
    if not args.ping and args.sleep is None and args.reporting is None:
        die('pass --ping, --sleep SECONDS or --sleep-reporting SECONDS')
    return asyncio.run(_call(args.url, args.token, args.sleep, args.timeout, args.reporting, args.every))


def cmd_calls(args: argparse.Namespace) -> int:
    calls = read_calls(args.since)
    if not calls:
        print(f'UNKNOWN — nothing has called the probe in the last {args.since}h.', file=sys.stderr)
        print(f'          Log: {log_path()}', file=sys.stderr)
        print('          Either it has not been run, or nothing reached it. Neither is', file=sys.stderr)
        print('          a finding on its own.', file=sys.stderr)
        return 1

    print(f'{len(calls)} call(s) in the last {args.since}h:')
    for entry in calls:
        print(f'  {entry["at"]}  {entry["tool"]:<6}  {entry["detail"]}')
    print()
    print('PASS — something reached the probe. Check the times against when the caller')
    print('       was due: a call at the expected minute is the finding, a call only')
    print('       when you ran it by hand is not.')
    return 0


def die(message: str) -> None:
    print(f'error: {message}', file=sys.stderr)
    raise SystemExit(2)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='mcp_probe.py', description=SUMMARY)
    sub = parser.add_subparsers(dest='command', required=True)
    listening = port()

    p = sub.add_parser('serve', help='run the probe server')
    p.add_argument('--port', type=int, default=listening)
    p.add_argument('--host', default='127.0.0.1')
    p.add_argument('--stdio', action='store_true', help='serve over stdio instead of HTTP')
    p.set_defaults(func=cmd_serve)

    p = sub.add_parser('call', help='call the probe and time it')
    p.add_argument('--url', default=f'http://127.0.0.1:{listening}/mcp')
    p.add_argument('--token', default=token())
    p.add_argument('--ping', action='store_true')
    p.add_argument('--sleep', type=int, metavar='SECONDS')
    p.add_argument('--sleep-reporting', type=int, metavar='SECONDS', dest='reporting')
    p.add_argument('--every', type=int, default=30, help='progress interval for --sleep-reporting')
    p.add_argument('--timeout', type=float, default=900.0, help='client ceiling, default 15 min')
    p.set_defaults(func=cmd_call)

    p = sub.add_parser('calls', help='what has called the probe, and when')
    p.add_argument('--since', type=int, default=24, help='hours to look back, default 24')
    p.set_defaults(func=cmd_calls)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == '__main__':
    raise SystemExit(main())
