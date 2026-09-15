"""Harry's clock, and the watchdog for the clock Harry does not own.

The watchdog is the only thing that tells a morning page that was never built apart from a
morning nobody checked, so every test here makes a real deadline pass rather than asserting
that the code which would notice exists.

The clock is driven by nudging real jobs on a real scheduler — `modify_job(next_run_time=…)`
— rather than by waiting for 05:00 or by calling the registered function directly. A test
that calls the function proves the capability works and nothing about the scheduler.
"""

from __future__ import annotations

import datetime as dt
import logging
import time
from collections.abc import Callable
from zoneinfo import ZoneInfo

import pytest

from harry.alerts import Alerts
from harry.loader import load
from harry.scheduler import WATCHDOG_ID, Jobs
from harry.store import Store

from .test_loader import root_with

BRUSSELS = ZoneInfo('Europe/Brussels')


class Somewhere:
    """Somewhere alerts go, that a test can read back."""

    def __init__(self) -> None:
        self.heard: list[str] = []

    def __call__(self, message: str) -> None:
        self.heard.append(message)


@pytest.fixture
def harry(tmp_path, monkeypatch):
    """A loaded Harry with a clock, a store and somewhere for alerts to go."""
    import harry.config

    current = harry.config.Settings(data_dir=tmp_path / 'data')
    monkeypatch.setattr(harry.config, 'get_settings', lambda: current)

    made: list[Jobs] = []
    sink = Somewhere()

    class Build:
        root = tmp_path / 'root'
        heard = sink.heard

        def store(self) -> Store:
            return Store(tmp_path / 'data' / 'jobs.json')

        def __call__(
            self,
            *capabilities: str,
            now: dt.datetime | Callable[[], dt.datetime] | None = None,
            scheduler: bool = True,
        ) -> Jobs:
            # `scheduler=False` is the second stack on one machine. Set before `Jobs` is
            # built, because the settings object is read at construction as well as at
            # start, and a test that flipped it afterwards would be testing neither state.
            nonlocal current
            current = harry.config.Settings(data_dir=tmp_path / 'data', scheduler_enabled=scheduler)
            # Only what is not there yet, so a test can build a second Jobs over the same
            # tree — which is what a restart looks like from here.
            root_with(self.root, *(name for name in capabilities if not (self.root / name).exists()))
            jobs = Jobs(
                load([self.root]),
                Alerts([sink]),
                self.store(),
                now=(now if callable(now) else (lambda: now)) if now is not None else None,
            )
            made.append(jobs)
            return jobs

    yield Build()

    for jobs in made:
        jobs.stop()


def fire_now(jobs: Jobs, name: str) -> None:
    """Bring a job's next run forward to now. The scheduler still runs it, its own way."""
    jobs.scheduler.modify_job(f'job:{name}', next_run_time=dt.datetime.now(dt.UTC))


def until(check, seconds: float = 3.0) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if check():
            return True
        time.sleep(0.02)
    return False


# ---------------------------------------------------------------------------
# The half Harry owns
# ---------------------------------------------------------------------------


def test_a_job_is_scheduled_for_its_cron_time_in_its_own_timezone(harry):
    jobs = harry('jobs/ticker')
    jobs.start()

    scheduled = jobs.scheduler.get_job('job:ticker')
    assert scheduled is not None
    assert scheduled.next_run_time.astimezone(BRUSSELS).hour == 5
    assert scheduled.next_run_time.astimezone(BRUSSELS).minute == 0


def test_the_same_cron_line_in_another_timezone_fires_somewhere_else(harry):
    """06:30 is a local time, not a UTC one — and so is 05:00."""
    jobs = harry('jobs/ticker', 'jobs/tokyo')
    jobs.start()

    brussels = jobs.scheduler.get_job('job:ticker').next_run_time
    tokyo = jobs.scheduler.get_job('job:tokyo').next_run_time

    assert brussels.astimezone(BRUSSELS).hour == 5
    assert tokyo.astimezone(ZoneInfo('Asia/Tokyo')).hour == 5
    assert brussels != tokyo


def test_firing_a_job_runs_what_the_capability_registered(harry):
    """Through the scheduler, not by calling the function — a test that calls the function
    proves the capability works and nothing about the clock."""
    jobs = harry('jobs/ticker')
    jobs.start()
    ran = harry.root / 'jobs' / 'ticker' / 'ran.txt'

    fire_now(jobs, 'ticker')

    assert until(ran.exists), 'the job never ran'
    assert ran.read_text(encoding='utf-8') == 'tick\n'


def test_a_job_still_running_is_not_started_again(harry, caplog):
    """A cache refresh that has stopped answering does not want a hundred copies of itself;
    it wants one, and somebody told."""
    jobs = harry('jobs/slowpoke')
    jobs.start()
    started = harry.root / 'jobs' / 'slowpoke' / 'started.txt'

    with caplog.at_level(logging.WARNING, logger='harry.scheduler'):
        fire_now(jobs, 'slowpoke')
        assert until(started.exists), 'the first run never started'
        fire_now(jobs, 'slowpoke')
        assert until(lambda: 'skipped slowpoke' in caplog.text), 'nothing noticed the overlap'

    assert started.read_text(encoding='utf-8') == 'in\n'
    assert 'the previous run has not finished' in caplog.text


def test_a_job_that_raises_is_logged_alerted_and_costs_only_itself(harry, caplog):
    jobs = harry('jobs/exploder', 'jobs/ticker')
    jobs.start()
    ran = harry.root / 'jobs' / 'ticker' / 'ran.txt'

    with caplog.at_level(logging.WARNING, logger='harry.scheduler'):
        fire_now(jobs, 'exploder')
        assert until(lambda: bool(harry.heard)), 'nobody was told the job failed'
        fire_now(jobs, 'ticker')
        assert until(ran.exists), 'the other job stopped running'

    assert harry.heard == ['exploder failed: ConnectionError: the feed host refused the connection']
    assert 'exploder raised' in caplog.text


def test_a_scheduled_job_with_no_code_is_said_out_loud(harry):
    """It would otherwise sit in /health as loaded and never do anything, which is the
    silence this whole feature exists to break."""
    jobs = harry('jobs/nocode')
    jobs.start()

    assert jobs.scheduler.get_job('job:nocode') is None
    assert harry.heard == ['nocode is scheduled but has no job.py, so nothing will run']


def test_nothing_to_run_is_a_working_harry(harry, caplog):
    jobs = harry()

    with caplog.at_level(logging.INFO, logger='harry.scheduler'):
        jobs.start()

    assert jobs.scheduler.running
    assert '0 job(s) on a schedule, 0 deadline(s) watched' in caplog.text


def test_the_watchdog_is_on_the_clock_too(harry):
    """Every five minutes, rather than once at each deadline: a check scheduled for exactly
    07:00 does not run if Harry was switched off at 07:00."""
    jobs = harry('jobs/morning-page')
    jobs.start()

    watchdog = jobs.scheduler.get_job(WATCHDOG_ID)
    assert watchdog is not None
    assert watchdog.trigger.interval == dt.timedelta(minutes=5)


# ---------------------------------------------------------------------------
# The half Harry only watches
# ---------------------------------------------------------------------------


def at(hour: int, minute: int = 0, day: int = 13) -> dt.datetime:
    return dt.datetime(2026, 9, day, hour, minute, tzinfo=BRUSSELS)


def test_a_deadline_that_passed_with_nothing_done_reaches_a_person(harry):
    jobs = harry('jobs/morning-page', now=at(7, 5))

    jobs.check_deadlines()

    assert harry.heard == ['morning-page has not run today. It was due by 07:00.']


def test_a_deadline_that_has_not_arrived_yet_says_nothing(harry):
    jobs = harry('jobs/morning-page', now=at(6, 55))

    jobs.check_deadlines()

    assert harry.heard == []


def test_a_job_finished_this_morning_says_nothing(harry):
    harry.store().mark_finished('morning-page', at(6, 45))
    jobs = harry('jobs/morning-page', now=at(7, 5))

    jobs.check_deadlines()

    assert harry.heard == []


def test_yesterdays_page_does_not_count_as_todays(harry):
    """A page built at 23:50 last night is not this morning's page."""
    harry.store().mark_finished('morning-page', at(23, 50, day=12))
    jobs = harry('jobs/morning-page', now=at(7, 5))

    jobs.check_deadlines()

    assert harry.heard == ['morning-page has not run today. It was due by 07:00.']


def test_a_missed_deadline_is_reported_once_however_often_the_check_runs(harry):
    jobs = harry('jobs/morning-page', now=at(7, 5))

    for _ in range(4):
        jobs.check_deadlines()

    assert len(harry.heard) == 1


def test_a_restart_does_not_repeat_a_deadline_already_reported(harry):
    """The alert layer suppresses a repeated key in memory, which a restart clears. For a
    fault reported once a day that would mean a second message on every deploy, so the date
    reported is written down beside the completion."""
    harry('jobs/morning-page', now=at(7, 0)).check_deadlines()
    assert len(harry.heard) == 1

    restarted = harry('jobs/morning-page', now=at(7, 5))
    restarted.check_deadlines()

    assert len(harry.heard) == 1


def test_an_alert_that_was_not_delivered_is_tried_again(harry, tmp_path, monkeypatch):
    """If nobody heard it, the deadline was not reported — marking it would mean the one
    morning it mattered went unheard."""
    import harry.config

    settings = harry.config.Settings(data_dir=tmp_path / 'data')
    monkeypatch.setattr(harry.config, 'get_settings', lambda: settings)

    def refuse(message: str) -> None:
        raise RuntimeError('the workspace is unreachable')

    root = root_with(tmp_path / 'root', 'jobs/morning-page')
    store = Store(tmp_path / 'data' / 'jobs.json')
    Jobs(load([root]), Alerts([refuse]), store, now=lambda: at(7, 5)).check_deadlines()

    assert store.reported('morning-page') is None

    heard: list[str] = []
    Jobs(load([root]), Alerts([heard.append]), store, now=lambda: at(7, 10)).check_deadlines()

    assert heard == ['morning-page has not run today. It was due by 07:00.']


def test_a_job_with_no_deadline_is_not_watched(harry):
    """Nothing said when it should be done by, so there is nothing to notice."""
    jobs = harry('jobs/undated', now=at(23, 59))

    jobs.check_deadlines()

    assert harry.heard == []


def test_a_scheduled_job_is_not_watched_for_a_deadline(harry):
    """Harry fires those itself. A missed one is a job that raised, not a silence."""
    jobs = harry('jobs/ticker', now=at(23, 59))

    jobs.check_deadlines()

    assert harry.heard == []


@pytest.mark.parametrize(
    ('utc_hour', 'expected'),
    [
        # In September Brussels is UTC+2, so 04:30 UTC is 06:30 there — before the deadline.
        (4, 0),
        # And 05:30 UTC is 07:30 there — after it.
        (5, 1),
    ],
)
def test_the_deadline_is_read_in_the_jobs_own_timezone(harry, utc_hour, expected):
    """A watchdog reading the machine's clock instead of the job's would be two hours out
    every day — reporting a miss at 05:00 Brussels time, in a channel somebody would then
    stop reading."""
    jobs = harry('jobs/morning-page', now=dt.datetime(2026, 9, 13, utc_hour, 30, tzinfo=dt.UTC))

    jobs.check_deadlines()

    assert len(harry.heard) == expected


# ---------------------------------------------------------------------------
# The watchdog on its own, and one bad declaration among good ones
# ---------------------------------------------------------------------------


def test_starting_harry_checks_the_deadlines_once(harry):
    """The only thing that reports a 07:00 miss on a machine that was switched off at
    07:00. Every other deadline test calls check_deadlines by hand, so without this one
    the start-up call could be deleted and nothing would notice."""
    jobs = harry('jobs/morning-page', now=at(7, 30))

    jobs.start()

    assert harry.heard == ['morning-page has not run today. It was due by 07:00.']


def test_the_watchdog_reports_when_the_scheduler_fires_it(harry):
    """Through the clock, not by calling the method — the interval job could be registered
    against anything at all and an assertion on its interval would still pass.

    The clock starts before the deadline so the check at start-up finds nothing, then moves
    past it. What reports the miss is the scheduler firing the watchdog on its own.
    """
    hand = [at(6, 55)]
    jobs = harry('jobs/morning-page', now=lambda: hand[0])
    jobs.start()
    assert harry.heard == [], 'the deadline had not passed yet'

    hand[0] = at(7, 30)
    jobs.scheduler.modify_job(WATCHDOG_ID, next_run_time=dt.datetime.now(dt.UTC))

    assert until(lambda: bool(harry.heard)), 'the watchdog never ran on its own'
    assert harry.heard == ['morning-page has not run today. It was due by 07:00.']


def test_a_job_failing_over_and_over_reports_once(harry):
    """Keyed on the job. A job failing every five minutes that reported every five minutes
    would empty the channel of anybody reading it."""
    jobs = harry('jobs/exploder')
    jobs.start()

    for _ in range(3):
        fire_now(jobs, 'exploder')
        time.sleep(0.15)

    assert until(lambda: bool(harry.heard))
    assert len(harry.heard) == 1


def test_a_timezone_that_is_not_a_timezone_costs_only_that_job(harry):
    """The loader skips a capability it cannot load. This is the same promise one step
    later — without it a single bad folder means no jobs are scheduled, the watchdog is
    never registered, and /health never answers to say which folder did it."""
    jobs = harry('jobs/badzone', 'jobs/ticker')

    jobs.start()

    assert jobs.scheduler.get_job('job:ticker') is not None, 'the good job was lost with the bad one'
    assert jobs.scheduler.get_job(WATCHDOG_ID) is not None, 'the watchdog was never registered'
    assert len(harry.heard) == 1
    assert harry.heard[0].startswith('badzone could not be scheduled: ZoneInfoNotFoundError')
    assert 'Mars/Olympus' in harry.heard[0], 'the reason should name what was wrong'


def test_a_deadline_that_will_not_parse_is_said_out_loud(harry):
    """Silently unwatching the job that most needed watching is the one outcome worse than
    a false alarm."""
    jobs = harry('jobs/baddeadline', 'jobs/morning-page', now=at(7, 30))

    jobs.check_deadlines()

    assert 'baddeadline could not be checked: ValueError' in harry.heard[0]
    assert 'morning-page has not run today. It was due by 07:00.' in harry.heard


def test_a_switched_off_job_is_not_watched(harry):
    """`enabled: false` is how you turn one off without deleting the folder, and a watchdog
    that kept reporting it would make that switch useless."""
    jobs = harry('jobs/switchedoff', now=at(23, 59))

    jobs.check_deadlines()

    assert harry.heard == []


# ---------------------------------------------------------------------------
# A second stack on one machine, with its clock off
# ---------------------------------------------------------------------------
#
# Two Harrys on one box would both watch the same deadlines, and the spare one would
# report a missed morning the real one delivered. These make the deadline actually pass
# and then ask who was told — the mute is the failure, so the alert is what is asserted
# on, not the setting that suppresses it.


def test_the_real_stack_reports_a_missed_morning_at_start_up(harry):
    """The control this pair exists to protect. Start with a deadline already past and
    somebody hears about it — this is the behaviour dev must not duplicate."""
    jobs = harry('jobs/morning-page', now=at(7, 5))

    jobs.start()

    assert harry.heard == ['morning-page has not run today. It was due by 07:00.']


def test_a_stack_with_the_scheduler_off_says_nothing_about_a_deadline_it_passed(harry):
    """The same morning, on the dev stack: silence.

    This is the whole reason the asymmetry exists. Delete the guard in `start()` and this
    goes red with the real stack's sentence in it, which is exactly the message that would
    have reached Slack about a page that was in fact delivered.
    """
    jobs = harry('jobs/morning-page', now=at(7, 5), scheduler=False)

    jobs.start()

    assert harry.heard == []


def test_a_stack_with_the_scheduler_off_registers_nothing_and_never_starts_the_clock(harry):
    """Not "it did not alert" but "there is nothing there to alert with".

    An empty scheduler that is running would pass a test about alerts today and hand a job
    to both stacks the day somebody adds one, so the clock itself has to be stopped.
    """
    jobs = harry('jobs/morning-page', 'jobs/refresh', scheduler=False)

    jobs.start()

    assert jobs.running is False
    assert jobs.scheduler.get_jobs() == []
    assert jobs.scheduler.get_job(WATCHDOG_ID) is None


def test_the_real_stack_does_register_the_watchdog(harry):
    """The other half of the pair: with the clock on, the watchdog is really there."""
    jobs = harry('jobs/morning-page', 'jobs/refresh')

    jobs.start()

    assert jobs.running is True
    assert jobs.scheduler.get_job(WATCHDOG_ID) is not None


def test_health_says_the_clock_is_off_rather_than_listing_deadlines_nobody_watches(harry):
    """How you tell the two stacks apart from outside, with no access to either's settings.

    Reporting `morning-page, due 07:00` from a stack that is not watching it would read as
    covered to the person checking at 07:10 — the one moment the answer has to be exact.
    """
    off = harry('jobs/morning-page', scheduler=False)
    off.start()

    assert off.as_health() == {'enabled': False, 'scheduled': [], 'watched': []}

    on = harry('jobs/morning-page')
    on.start()
    watching = on.as_health()

    assert watching['enabled'] is True
    assert [w['name'] for w in watching['watched']] == ['morning-page']
