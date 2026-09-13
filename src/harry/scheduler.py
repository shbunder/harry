"""Harry's clock, and the watchdog for the clock Harry does not own.

Two halves, and the second is the one that matters.

**Harry owns the clock for its own heuristic work.** Refresh a cache at 05:00, retry a
failed push, check whether a credential still works. Each is a rule that can be written down
in advance, so Harry can run it.

**Harry does not own the clock for anything that needs judgement.** A Claude scheduled task
fires the morning page, because choosing what goes on it is the whole reason Harry does not
call a model. That split has one cost: **an external trigger cannot report its own
absence.** A task that never fires produces silence, and silence looks exactly like a
morning you did not check.

The watchdog is the only thing that tells those two apart. It **polls** — every five
minutes, and once at start-up — rather than running at each deadline, because a check
scheduled for exactly 07:00 does not run if Harry was switched off at 07:00, and that is
precisely the morning worth hearing about. Late is the right failure here; never is not.

APScheduler rather than cron: the container has no cron daemon, and a job needs the app's
own configuration and the objects the loader built.
"""

from __future__ import annotations

import datetime as dt
import logging
from collections.abc import Callable, Iterable
from typing import Any
from zoneinfo import ZoneInfo

from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_MAX_INSTANCES, JobEvent
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from harry.alerts import Alerts
from harry.config import get_settings
from harry.registry import Capability, Catalogue
from harry.store import Store

LOG = logging.getLogger('harry.scheduler')

WATCHDOG_ID = 'harry:deadlines'
EVERY = dt.timedelta(minutes=5)
"""How often the watchdog asks. A deadline is written to the minute, so the answer is at
most five minutes late — against never, which is what a check at the deadline gives you on
a machine that was switched off at the deadline."""

JOB_PREFIX = 'job:'


class Jobs:
    """Everything Harry runs on a clock, and everything it watches somebody else's clock for."""

    def __init__(
        self,
        catalogue: Catalogue,
        alerts: Alerts,
        store: Store,
        *,
        now: Callable[[], dt.datetime] | None = None,
    ) -> None:
        self._catalogue = catalogue
        self._alerts = alerts
        self._store = store
        self._now = now or (lambda: dt.datetime.now(dt.UTC))
        self._scheduler = BackgroundScheduler(timezone=get_settings().timezone)
        self._scheduler.add_listener(self._job_failed, EVENT_JOB_ERROR)
        self._scheduler.add_listener(self._job_was_still_running, EVENT_JOB_MAX_INSTANCES)

    @property
    def scheduler(self) -> BackgroundScheduler:
        """The clock itself, for anything that needs to ask it what is scheduled and when."""
        return self._scheduler

    # -- starting and stopping ----------------------------------------------

    def start(self) -> None:
        """Schedule everything, then check the deadlines once.

        The check at start-up is what reports a deadline that passed while Harry was off.
        """
        for capability in self._scheduled():
            self._safely(capability, self._schedule, 'be scheduled')

        self._scheduler.add_job(
            self.check_deadlines,
            IntervalTrigger(seconds=int(EVERY.total_seconds())),
            id=WATCHDOG_ID,
            max_instances=1,
            coalesce=True,
        )
        self._scheduler.start()
        LOG.info('%d job(s) on a schedule, %d deadline(s) watched', len(self._scheduled()), len(self._watched()))
        self.check_deadlines()

    def stop(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)

    # -- the half Harry owns -------------------------------------------------

    def _scheduled(self) -> list[Capability]:
        return [c for c in self._jobs() if _declaration(c).get('trigger') == 'schedule']

    def _schedule(self, capability: Capability) -> None:
        declaration = _declaration(capability)
        if capability.target is None:
            # A `trigger: schedule` job with no Python is a job that would silently never
            # do anything, which is the failure this whole feature exists to break.
            self._alerts.send(
                f'{capability.name} is scheduled but has no job.py, so nothing will run',
                key=f'job:{capability.name}:nothing-to-run',
            )
            return

        self._scheduler.add_job(
            capability.target,
            CronTrigger.from_crontab(str(declaration['schedule']), timezone=_zone(declaration)),
            id=f'{JOB_PREFIX}{capability.name}',
            name=capability.name,
            # One at a time. A cache refresh that has stopped answering does not want a
            # hundred copies of itself; it wants one, and somebody told.
            max_instances=1,
            # A machine asleep through three fire times runs the job once on waking, not
            # three times.
            coalesce=True,
        )
        LOG.info('%s scheduled: %s (%s)', capability.name, declaration['schedule'], _zone(declaration))

    def _job_failed(self, event: JobEvent) -> None:
        name = _name_of(event.job_id)
        error = getattr(event, 'exception', None)
        LOG.warning('job %s raised: %s: %s', name, type(error).__name__, error)
        self._alerts.send(f'{name} failed: {type(error).__name__}: {error}', key=f'job:{name}:failed')

    def _job_was_still_running(self, event: JobEvent) -> None:
        """Harry's own line, not APScheduler's.

        APScheduler logs its own warning when `max_instances` bites, so a test asserting
        that something logged would pass whether or not Harry noticed at all.
        """
        LOG.warning('skipped %s: the previous run has not finished', _name_of(event.job_id))

    # -- the half Harry only watches -----------------------------------------

    def _watched(self) -> list[Capability]:
        """Jobs somebody else triggers, that said when they should be done by.

        No deadline means nothing to notice. `.claude/rules/capability-shape.md` requires
        one on every `trigger: claude` job for exactly this reason, and the gate enforces it
        — so a job without one got here from a root that never passed anybody's gate.
        """
        return [
            c for c in self._jobs() if _declaration(c).get('trigger') == 'claude' and _declaration(c).get('deadline')
        ]

    def check_deadlines(self) -> None:
        """Anything due by now and not done, said once."""
        for capability in self._watched():
            self._safely(capability, self._check, 'be checked')

    def _safely(self, capability: Capability, what: Callable[[Capability], None], doing: str) -> None:
        """One job's declaration cannot take the others down, or Harry with them.

        The loader skips a capability it cannot load. This is the same promise one step
        later: a timezone that is not a timezone, a cron line that is not a cron line, a
        `trigger: schedule` with no schedule. Without it a single bad folder means no jobs
        are scheduled, the watchdog is never registered, and `/health` — the endpoint that
        would have named the broken capability — never answers either.

        `make lint` does not save you: it validates `.harry/`, never a folder that arrived
        through `$HARRY_CAPABILITIES_DIR` or was dropped on the NUC by hand.
        """
        try:
            what(capability)
        except Exception as error:  # noqa: BLE001 — one folder, one failure
            reason = f'{type(error).__name__}: {error}'
            LOG.warning('%s could not %s: %s', capability.name, doing, reason)
            self._alerts.send(f'{capability.name} could not {doing}: {reason}', key=f'job:{capability.name}:broken')

    def _check(self, capability: Capability) -> None:
        declaration = _declaration(capability)
        zone = _zone(declaration)
        here = self._now().astimezone(zone)
        due = dt.time.fromisoformat(str(declaration['deadline']))
        if here.timetz().replace(tzinfo=None) < due:
            return

        today = here.date()
        if self._store.reported(capability.name) == today:
            return

        finished = self._store.last_finished(capability.name)
        if finished is not None and finished.astimezone(zone).date() == today:
            return

        said = self._alerts.send(
            f'{capability.name} has not run today. It was due by {declaration["deadline"]}.',
            key=f'deadline:{capability.name}:{today}',
        )
        if said:
            # Only when somebody was actually told. Marking it reported after a failed
            # delivery would mean the one morning it mattered went unheard.
            self._store.mark_reported(capability.name, today)

    # -- what the loader found ------------------------------------------------

    def _jobs(self) -> Iterable[Capability]:
        return [c for c in self._catalogue.loaded if c.kind == 'job']

    def as_health(self) -> dict[str, Any]:
        """What the clock is doing, for `/health`.

        "The watchdog has been quiet — is it even watching?" is a real question at 07:10,
        and the honest answer is the list of what is watched and when each was last
        finished. Job names and times only; no setting values, secret or otherwise.
        """
        remembered = self._store.as_dict()
        return {
            'scheduled': [
                {'name': c.name, 'next_run': self._next_run(c.name)} for c in sorted(self._scheduled(), key=_by_name)
            ],
            'watched': [
                {
                    'name': c.name,
                    'deadline': str(_declaration(c).get('deadline')),
                    'last_finished': remembered.get(c.name, {}).get('finished'),
                }
                for c in sorted(self._watched(), key=_by_name)
            ],
        }

    def _next_run(self, name: str) -> str | None:
        scheduled = self._scheduler.get_job(f'{JOB_PREFIX}{name}')
        when = getattr(scheduled, 'next_run_time', None)
        return when.isoformat() if when else None


def _by_name(capability: Capability) -> str:
    return capability.name


def _declaration(capability: Capability) -> dict[str, Any]:
    return dict(capability.context.declaration) if capability.context is not None else {}


def _zone(declaration: dict[str, Any]) -> ZoneInfo:
    """The job's own timezone, or Harry's. 06:30 is a local time, not a UTC one."""
    return ZoneInfo(str(declaration.get('timezone') or get_settings().timezone))


def _name_of(job_id: str) -> str:
    return job_id.removeprefix(JOB_PREFIX)
