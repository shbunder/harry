"""What Harry remembers between restarts.

One JSON file under the data volume, holding two facts per job: when it last finished, and
which deadline has already been reported. That is the whole store, and it is the whole
store on purpose.

**Not SQLite.** This is a handful of keys, read once at start-up and written a few times a
day. An index buys nothing, and a file somebody can `cat` while wondering why the watchdog
is quiet is worth more than one they cannot. When something needs a query, SQLite arrives
with it.

**Durable rather than in memory**, because the alternative fails in a specific and awful
way: a restart would lose every completion, the watchdog would report a missed deadline for
a morning page delivered an hour earlier, and a false alarm on every deploy is exactly how
a channel gets muted.

Both halves of the file are best effort. A store that cannot be read starts empty and says
so; a store that cannot be written says so and carries on. Refusing to start because a
cache file is unreadable would take down Harry to protect a timestamp.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
from pathlib import Path
from typing import Any

LOG = logging.getLogger('harry.store')

FINISHED = 'finished'
REPORTED = 'reported'


class Store:
    """Harry's memory of what has happened, per job."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._jobs: dict[str, dict[str, str]] = self._read()

    def _read(self) -> dict[str, dict[str, str]]:
        if not self.path.is_file():
            return {}
        try:
            loaded = json.loads(self.path.read_text(encoding='utf-8'))
        except (OSError, ValueError) as error:
            # An empty record makes the next watchdog check alert for everything, which is
            # a false alarm somebody notices and fixes. The other direction — refusing to
            # start — takes Harry down to protect a timestamp.
            LOG.warning('could not read %s, starting with an empty record: %s', self.path, error)
            return {}
        jobs = loaded.get('jobs') if isinstance(loaded, dict) else None
        return jobs if isinstance(jobs, dict) else {}

    def _write(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps({'jobs': self._jobs}, indent=2, sort_keys=True), encoding='utf-8')
        except OSError as error:
            # Said out loud every time: a data volume that cannot be written is a real
            # problem, and the visible symptom otherwise is a watchdog alerting about a job
            # that ran.
            LOG.warning('could not write %s: %s', self.path, error)

    # -- what a job did ------------------------------------------------------

    def mark_finished(self, job: str, at: dt.datetime) -> None:
        self._jobs.setdefault(job, {})[FINISHED] = at.isoformat()
        self._write()

    def last_finished(self, job: str) -> dt.datetime | None:
        return _as_datetime(self._jobs.get(job, {}).get(FINISHED))

    # -- what has already been said -----------------------------------------

    def mark_reported(self, job: str, day: dt.date) -> None:
        """Remember that today's missed deadline has been reported.

        Here rather than in the alert layer's own 24-hour suppression, because that is in
        memory: right for a fault repeating every five minutes, wrong for one reported once
        a day, where the second report would arrive on every restart.
        """
        self._jobs.setdefault(job, {})[REPORTED] = day.isoformat()
        self._write()

    def reported(self, job: str) -> dt.date | None:
        raw = self._jobs.get(job, {}).get(REPORTED)
        try:
            return dt.date.fromisoformat(raw) if raw else None
        except ValueError:
            return None

    def as_dict(self) -> dict[str, Any]:
        """What is on disk, for anything that wants to look. Copied, not the live mapping."""
        return {job: dict(facts) for job, facts in self._jobs.items()}


def _as_datetime(raw: str | None) -> dt.datetime | None:
    try:
        return dt.datetime.fromisoformat(raw) if raw else None
    except ValueError:
        return None
