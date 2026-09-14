"""Your calendar, over CalDAV, one day at a time.

## Why the recurrence is done here

CalDAV has a server-side answer for repeating events: ask for a date range with
`expand=True` and get one object per occurrence. **iCloud accepts that request and ignores
it**, returning the start of the series instead — measured against a real account, where a
search for one day came back with an event dated a week earlier.

An agenda built on that prints last Monday beside a meeting happening this morning, and one
that filters by date afterwards drops the meeting entirely. The second failure is the
dangerous one: a recurring meeting missing from the page looks exactly like a morning it was
cancelled. So `server_expand` is not passed at all — asking for something that is silently
ignored makes the code read as though somebody else handles it.

## Why every event goes into one calendar before expanding

A moved or cancelled instance arrives from the server as a *separate* object carrying a
`RECURRENCE-ID`, and it only suppresses the generated occurrence if the expander can see
both at once. Expanding each object on its own gives you the standup twice: once at its old
time and once at its new one.

## Why this raises where the other sources answer

`weather.forecast()` and `news.search()` return `available: false`, because a forecast
nobody can get is still an answer. An agenda is different: **an empty list is a free day**,
which is information a person acts on. If a dead calendar also returned an empty list the
page would say "Nothing on today" on a morning with three meetings in it. So a day with
nothing on it returns `[]` and a calendar that cannot be read raises.
"""

from __future__ import annotations

import datetime as dt
import logging
from collections.abc import Callable, Iterable
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import caldav
import icalendar
import recurring_ical_events
from caldav.lib.error import AuthorizationError, DAVError
from niquests.exceptions import Timeout

from harry.sdk import Context, Registry

CALDAV = 'https://caldav.icloud.com'

TIMEOUT = 15
"""Seconds **per request**, which is what caldav's client takes and not a ceiling on the
whole read.

CalDAV is several round trips: discovery, then one report per calendar. The account this was
built against has 17 calendars, so an iCloud that accepts connections and never answers costs
minutes rather than seconds. The Slack sentence says "per request" for that reason — a line
promising a total nothing enforces is worse than no number.

Naming which calendars matter in `CALENDARS` is the way to bound it, and the runbook says so.
"""

ALL_DAY = 'all day'
"""What `at` says for an event with a date and no time. Not an empty string, which reads as
a missing value, and not "00:00", which is a time nobody set."""


class Unreachable(Exception):
    """The calendar could not be read. Carries what to do, never the protocol's account."""


class Agenda:
    """One account, one day at a time."""

    def __init__(
        self,
        username: str,
        password: str,
        calendars: Iterable[str],
        zone: ZoneInfo,
        log: logging.Logger,
        alert: Callable[..., bool],
        connect: Callable[[str, str], Any] | None = None,
    ) -> None:
        self._username = username
        self._password = password
        self._wanted = [name.strip() for name in calendars if name.strip()]
        self._zone = zone
        self._log = log
        self._alert = alert
        self._connect = connect or _reach_icloud
        self._principal: Any | None = None

    # -- what the digest calls ------------------------------------------------

    def today(self) -> list[dict]:
        """Today's agenda, earliest first. The signature the morning page was built for."""
        return self.on(dt.datetime.now(self._zone).date())

    def on(self, day: dt.date | str) -> list[dict]:
        """One day, as `[{at, title, where}]`.

        An empty list is a free day. A calendar that cannot be read raises, so the page can
        tell "nothing on" from "nobody knows".
        """
        wanted = _a_date(day)
        start = dt.datetime.combine(wanted, dt.time.min, tzinfo=self._zone)
        found = self._read(start, start + dt.timedelta(days=1))
        return sorted(found, key=lambda event: (event['at'] != ALL_DAY, event['at']))

    # -- the work -------------------------------------------------------------

    def _read(self, start: dt.datetime, end: dt.datetime) -> list[dict]:
        try:
            calendars = self._calendars()
            merged = icalendar.Calendar()
            for calendar in calendars:
                self._collect(calendar, start, end, merged)
        except AuthorizationError as error:
            raise self._give_up(
                'the password was refused — make a new app-specific password at account.apple.com', key='refused'
            ) from error
        except (DAVError, OSError) as error:
            raise self._give_up(_why(error), key='unreachable') from error
        except Exception as error:  # noqa: BLE001 — anything escaping here degrades the page
            # with nobody told, which is the silence this connector exists to break. icalendar
            # and lxml both raise types that are neither DAVError nor OSError.
            self._log.exception('the calendar raised something this connector does not handle')
            raise self._give_up(
                'iCloud answered something this connector does not understand', key='unreadable'
            ) from error

        occurrences = recurring_ical_events.of(merged, skip_bad_series=True).between(start, end)
        return [shaped for occurrence in occurrences if (shaped := self._shape(occurrence)) is not None]

    def _collect(self, calendar: Any, start: dt.datetime, end: dt.datetime, merged: icalendar.Calendar) -> None:
        """Every event object touching the window, into one calendar.

        `server_expand` is deliberately not passed. iCloud ignores it, and a `True` here
        would read as though the occurrences arriving are the server's work.
        """
        for found in calendar.search(start=start, end=end, event=True):
            try:
                for component in found.icalendar_instance.walk():
                    if component.name == 'VTIMEZONE':
                        merged.add_component(component)
                    elif component.name == 'VEVENT' and self._readable(component):
                        merged.add_component(component)
            except Exception as error:  # noqa: BLE001 — icalendar raises a dozen types on a
                # malformed entry, and one bad event must cost one event rather than the day.
                self._log.warning('skipping an event that would not parse: %s', type(error).__name__)

    def _readable(self, event: Any) -> bool:
        """Whether this event's start can be read at all.

        `recurring_ical_events` is asked to skip a series it cannot expand, and it does —
        silently, inside the library. Silently is the problem: a recurring meeting vanishing
        from the page with no trace is the failure the whole connector is arranged against.
        So the start is touched here, where a skip can be said out loud.
        """
        try:
            starts = event.get('DTSTART')
            if starts is not None:
                _ = starts.dt
        except Exception as error:  # noqa: BLE001 — icalendar raises several types for this
            self._log.warning(
                'skipping %r: its start time cannot be read (%s)',
                str(event.get('SUMMARY') or 'an event with no title'),
                type(error).__name__,
            )
            return False
        return True

    def _calendars(self) -> list[Any]:
        """The calendars to read. Everything, unless somebody named some."""
        if self._principal is None:
            self._principal = self._connect(self._username, self._password).principal()
        every = self._principal.calendars()
        if not self._wanted:
            return every

        by_name = {str(calendar.name): calendar for calendar in every}
        for name in self._wanted:
            if name not in by_name:
                self._log.warning('no calendar called %r on this account; skipping it', name)
        return [by_name[name] for name in self._wanted if name in by_name]

    def _shape(self, occurrence: Any) -> dict | None:
        """One occurrence into the three fields the page needs, or None if it has no start."""
        starts = occurrence.get('DTSTART')
        if starts is None:
            return None
        when = starts.dt
        if isinstance(when, dt.datetime):
            at = when.astimezone(self._zone).strftime('%H:%M')
        else:
            # A date with no time. iCalendar says that is an all-day event, and the page
            # should say so rather than invent midnight.
            at = ALL_DAY
        return {
            'at': at,
            'title': str(occurrence.get('SUMMARY') or '').strip(),
            'where': str(occurrence.get('LOCATION') or '').strip(),
        }

    def _give_up(self, why: str, key: str) -> Unreachable:
        """One line, once a day **per fault**. Never the password, the URL or the response.

        Keyed by what went wrong rather than by the connector. One key for everything would
        let a transient blip at any hour spend the day's budget, and the sentence a person
        can actually act on — *make a new app-specific password* — would never arrive. This
        tool is callable from any session, so that blip is not hypothetical.
        """
        self._log.warning('could not read the calendar: %s', why)
        self._alert(f'iCloud: {why}', key=key)
        self._principal = None
        return Unreachable(why)


def _a_date(day: dt.date | str) -> dt.date:
    """A date from what the caller gave, or a message saying what was wanted."""
    if isinstance(day, dt.date) and not isinstance(day, dt.datetime):
        return day
    if isinstance(day, dt.datetime):
        return day.date()
    try:
        return dt.date.fromisoformat(str(day))
    except ValueError as error:
        raise ValueError(f'{day!r} is not a date — write it as 2026-09-14') from error


def _why(error: Exception) -> str:
    """What to tell somebody, from what went wrong. No traceback, no URL, no response body.

    This sentence goes to Slack, and the request that produced it carried the password in a
    header.
    """
    if isinstance(error, Timeout):
        return f'iCloud stopped answering ({TIMEOUT}s per request)'
    if isinstance(error, OSError):
        return 'iCloud could not be reached'
    return 'iCloud answered something this connector does not understand'


def _reach_icloud(username: str, password: str) -> caldav.DAVClient:
    """A CalDAV client for one account. Nothing here is written to disk."""
    return caldav.DAVClient(url=CALDAV, username=username, password=password, timeout=TIMEOUT)


def register(registry: Registry, context: Context) -> None:
    wanted = str(context.config['timezone'])
    try:
        zone = ZoneInfo(wanted)
    except (ZoneInfoNotFoundError, ValueError):
        context.log.warning('no zone called %r; reading the calendar in UTC instead', wanted)
        zone = ZoneInfo('UTC')

    registry.connector(
        Agenda(
            username=str(context.config['username']),
            password=str(context.config['app_password']),
            calendars=str(context.config.get('calendars') or '').split(','),
            zone=zone,
            log=context.log,
            alert=context.alert,
        )
    )
