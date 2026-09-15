"""The job that owns the morning, and the watchdog that notices when it did not happen.

**An external trigger cannot report its own absence.** A Claude scheduled task that never
fires produces silence, and silence looks exactly like a morning nobody checked. The watchdog
is the only thing that tells the difference — so the question this file answers is not "does
the folder exist" but "does anything actually watch it".
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from harry.loader import load
from harry.mcp import MARK_DONE
from harry.scheduler import Jobs
from harry.store import Store

REPO = Path(__file__).parent.parent
JOB = REPO / '.harry' / 'jobs' / 'morning-page' / 'JOB.md'


def declaration() -> str:
    return JOB.read_text(encoding='utf-8')


def test_the_job_is_one_markdown_file_with_no_python_beside_it():
    """A job is a brief, not a program. The moment it grows a `job.py` somebody has written
    the choosing into Harry, which is the one thing this design exists to prevent."""
    assert JOB.is_file()
    assert sorted(p.name for p in JOB.parent.iterdir()) == ['JOB.md']


def test_the_clock_lives_outside_harry_and_the_deadline_lives_inside_it():
    """`trigger: claude` means a Claude scheduled task owns the clock. A `schedule:` here
    would be a second clock that can disagree with it — and `make lint` refuses one."""
    front = declaration().split('---')[1]

    assert 'trigger: claude' in front
    assert 'schedule:' not in front, 'two clocks that can disagree'
    assert 'deadline: "07:00"' in front, 'nothing can notice a miss without one'


def test_the_watchdog_actually_watches_this_job(tmp_path):
    """The deciding question. The declaration is right, the rule requires it, the gate
    enforces it — and none of that is the scheduler having the job on its list."""
    from harry.alerts import Alerts

    jobs = Jobs(load(), Alerts(), Store(tmp_path / 'jobs.json'))

    watched = [c.name for c in jobs._watched()]  # noqa: SLF001 — nothing else exposes the list

    assert 'morning-page' in watched, 'the job nobody would notice missing'


def test_a_morning_that_never_happened_reaches_slack(tmp_path):
    """The failure this job is arranged against: the task did not fire, so there is no error
    anywhere — only a tablet with yesterday's paper on it."""

    from harry.alerts import Alerts

    heard: list[str] = []
    alerts = Alerts()
    alerts._sinks = [heard.append]  # noqa: SLF001 — no Slack connector loads on this machine

    # Eight in the morning in Brussels: an hour past the deadline, and nothing marked done.
    jobs = Jobs(
        load(),
        alerts,
        Store(tmp_path / 'jobs.json'),
        now=lambda: dt.datetime(2026, 9, 16, 6, 0, tzinfo=dt.UTC),
    )

    jobs.check_deadlines()

    assert any('morning-page has not run today' in said for said in heard), heard
    assert any('07:00' in said for said in heard)


def test_the_brief_tells_claude_to_close_the_job_with_the_tool_that_exists(tmp_path):
    """The watchdog only goes quiet because something marked the job done. A brief that named
    a tool which does not exist would leave the alert firing every morning of a working
    Harry, which is how a channel gets muted."""
    body = declaration()

    assert MARK_DONE in body, f'the brief does not tell Claude to call {MARK_DONE}'


def test_the_brief_asks_for_the_two_tools_by_name():
    """A brief is served to Claude as a prompt and nothing parses it, so the only thing
    keeping it honest is that the names in it are names that exist."""
    body = declaration()
    known = {c.name for c in load().loaded if c.kind == 'tool'}

    for named in ('digest_list_candidates', 'digest_build'):
        assert named in body, f'the brief never asks for {named}'
        assert named in known, f'{named} is named in the brief and does not load'
