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

SUMMARY = (__doc__ or '').partition('\n')[0]

DEFAULT_TOKEN = 'probe-token-not-a-secret'
DEFAULT_LOG = Path.home() / '.harry-probe' / 'calls.jsonl'


def token() -> str:
    """The bearer token. Read at call time, not import time, so tests can set it."""
    return os.environ.get('HARRY_API_TOKEN') or DEFAULT_TOKEN


def log_path() -> Path:
    return Path(os.environ.get('HARRY_PROBE_LOG') or DEFAULT_LOG)


def record(tool: str, detail: str) -> None:
    """Append one call. Best effort: a probe that cannot write its log still answers."""
    path = log_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        entry = {'at': dt.datetime.now().isoformat(timespec='seconds'), 'tool': tool, 'detail': detail}
        with path.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(entry) + '\n')
    except OSError:
        pass


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


async def sleep_reporting(seconds: int = 600, every: int = 30, context: Context | None = None) -> str:
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


async def _call(url: str, bearer: str, seconds: int | None, timeout: float) -> int:
    started = time.time()
    try:
        # `auth=<str>` is the bearer shorthand — the raw token, not "Bearer <token>".
        async with Client(url, auth=bearer, timeout=timeout) as client:
            names = sorted(tool.name for tool in await client.list_tools())
            print(f'connected — tools: {", ".join(names)}')

            started = time.time()
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
        print(f'FAIL — {type(error).__name__} after {time.time() - started:.1f}s: {error}', file=sys.stderr)
        print('       A connection error is UNKNOWN, not a finding — the server may', file=sys.stderr)
        print('       simply not be up. A timeout at a specific length is a finding.', file=sys.stderr)
        return 1


def cmd_call(args: argparse.Namespace) -> int:
    if not args.ping and args.sleep is None:
        die('pass --ping or --sleep SECONDS')
    return asyncio.run(_call(args.url, args.token, args.sleep, args.timeout))


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
    port = int(os.environ.get('HARRY_PORT', 7430))

    p = sub.add_parser('serve', help='run the probe server')
    p.add_argument('--port', type=int, default=port)
    p.add_argument('--host', default='127.0.0.1')
    p.add_argument('--stdio', action='store_true', help='serve over stdio instead of HTTP')
    p.set_defaults(func=cmd_serve)

    p = sub.add_parser('call', help='call the probe and time it')
    p.add_argument('--url', default=f'http://127.0.0.1:{port}/mcp')
    p.add_argument('--token', default=token())
    p.add_argument('--ping', action='store_true')
    p.add_argument('--sleep', type=int, metavar='SECONDS')
    p.add_argument('--sleep-reporting', type=int, metavar='SECONDS', dest='reporting')
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
