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
from dataclasses import dataclass
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import caldav
import httpx
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

LINK_TIMEOUT = 20.0
"""Seconds for one published link. The measured Outlook feed is 189 KB — a whole calendar in
one document rather than a query for one day, which is why this is longer than a CalDAV
request."""

FRESH_FOR = dt.timedelta(minutes=5)
"""How long a fetched link is reused. Asking about a week is seven calls, and each would
otherwise pull the whole document again. Only a success is cached: a link that failed is
retried on the next call rather than served from an older copy, because an agenda that
silently ages is the same lie as a partial one."""

ALL_DAY = 'all day'
"""What `at` says for an event with a date and no time. Not an empty string, which reads as
a missing value, and not "00:00", which is a time nobody set."""

UNNAMED = 'Calendar'
"""What a calendar that will not give its name is filed under. Its events still reach the
page — in the uncoloured grey, because colour is keyed on the name — since a nameless
calendar is a cosmetic problem and a missing afternoon is not."""


@dataclass(frozen=True)
class Link:
    """One published calendar. `label` is what a person reads; `url` is the credential."""

    label: str
    url: str


def read_links(setting: str, log: logging.Logger) -> list[Link]:
    """`Name=url|Name=url` into links, skipping anything malformed.

    Split on the first `=` so a URL may carry as many more as it likes — the Outlook ones do.
    A malformed entry costs one link and a log line, because one typo in a list of three
    should not cost the other two.

    **The URL never reaches the log**, here or anywhere: the random segment in it is the
    password, so a bad entry is reported by position rather than by content.
    """
    links: list[Link] = []
    for position, entry in enumerate(setting.split('|'), start=1):
        entry = entry.strip()
        if not entry:
            continue
        label, _, url = entry.partition('=')
        if not (label.strip() and url.strip().startswith('http')):
            log.warning('skipping SUBSCRIBED entry %d: it is not Name=https://…', position)
            continue
        links.append(Link(label=label.strip(), url=url.strip()))
    return links


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
        links: Iterable[Link] = (),
        now: Callable[[], dt.datetime] = lambda: dt.datetime.now(dt.timezone.utc),
    ) -> None:
        self._username = username
        self._password = password
        self._wanted = [name.strip() for name in calendars if name.strip()]
        self._links = list(links)
        self._now = now
        self._fetched: dict[str, tuple[dt.datetime, str]] = {}
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
        """One day, as `[{at, ends, title, where, calendar}]`.

        An empty list is a free day. A calendar that cannot be read raises, so the page can
        tell "nothing on" from "nobody knows".
        """
        wanted = _a_date(day)
        start = dt.datetime.combine(wanted, dt.time.min, tzinfo=self._zone)
        found = self._read(start, start + dt.timedelta(days=1))
        return sorted(found, key=lambda event: (event['at'] != ALL_DAY, event['at']))

    # -- the work -------------------------------------------------------------

    def _read(self, start: dt.datetime, end: dt.datetime) -> list[dict]:
        """Every source, read and expanded on its own.

        One document per calendar rather than one merged document, because the page colours
        by calendar and the merge is exactly where that fact is lost. It costs one expansion
        per source instead of one for everything; a personal account has a handful.
        """
        sources: list[tuple[str, icalendar.Calendar]] = []
        try:
            for calendar in self._calendars():
                merged = icalendar.Calendar()
                self._collect(calendar, start, end, merged)
                sources.append((self._name_of(calendar), merged))
            for link in self._links:
                merged = icalendar.Calendar()
                self._collect_link(link, merged)
                sources.append((link.label, merged))
        except AuthorizationError as error:
            raise self._give_up(
                'the password was refused — make a new app-specific password at account.apple.com', key='refused'
            ) from error
        except Unreachable:
            # Already reported, with a sentence naming which calendar and what to do about
            # it. Re-wrapping would replace that with "something this connector does not
            # understand" and alert a second time under a different key.
            raise
        except (DAVError, OSError) as error:
            raise self._give_up(_why(error), key='unreachable') from error
        except Exception as error:  # noqa: BLE001 — anything escaping here degrades the page
            # with nobody told, which is the silence this connector exists to break. icalendar
            # and lxml both raise types that are neither DAVError nor OSError.
            self._log.exception('the calendar raised something this connector does not handle')
            raise self._give_up(
                'iCloud answered something this connector does not understand', key='unreadable'
            ) from error

        found: list[dict] = []
        for name, document in sources:
            occurrences = recurring_ical_events.of(document, skip_bad_series=True).between(start, end)
            found += [shaped for one in occurrences if (shaped := self._shape(one, name)) is not None]
        return found

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

    def _collect_link(self, link: Link, merged: icalendar.Calendar) -> None:
        """One published calendar, into the same document as everything else.

        **A link that cannot be read fails the whole agenda**, rather than quietly leaving
        its meetings out. Everywhere else in Harry a dead source costs its own section; here
        the section *is* the day, and a day missing your work meetings looks exactly like a
        quiet one. A missing agenda sends you to your phone; a partial one does not.
        """
        document = self._fetch(link)
        for component in document.walk():
            if component.name == 'VTIMEZONE':
                merged.add_component(component)
            elif component.name == 'VEVENT' and self._readable(component):
                merged.add_component(component)

    def _fetch(self, link: Link) -> icalendar.Calendar:
        """A link's document, at most once every `FRESH_FOR`.

        Neither the exception nor the alert carries the URL. The random segment in it is the
        password, so the label is what a person is given — which is also the thing they can
        act on: getting a fresh link from whoever publishes that calendar.
        """
        cached = self._fetched.get(link.url)
        if cached and self._now() - cached[0] < FRESH_FOR:
            self._log.debug('%s is still fresh', link.label)
            return icalendar.Calendar.from_ical(cached[1])

        try:
            response = httpx.get(link.url, timeout=LINK_TIMEOUT, follow_redirects=True)
            response.raise_for_status()
        except httpx.HTTPError as error:
            # `from None`, not `from error`. httpx puts the request URL inside its own
            # exception message, and a published link's URL *is* the credential — so a
            # chained cause hands it to whatever logs the traceback. FastMCP does exactly
            # that for a failing tool call, at ERROR, whatever HARRY_LOG_LEVEL says.
            # Nothing diagnostic is lost: the sentence below names the link and what to do.
            raise self._give_up(_why_link(error, link.label), key=f'link:{link.label}') from None

        try:
            document = icalendar.Calendar.from_ical(response.text)
        except Exception:  # noqa: BLE001 — icalendar raises several types, and an
            # expired link answers 200 with a sign-in page, which is the common case here.
            raise self._give_up(
                f'{link.label} answered something that is not a calendar, which is what an expired '
                'link does. Ask whoever publishes that calendar for a fresh link and put it in SUBSCRIBED',
                key=f'link:{link.label}',
            ) from None  # icalendar quotes the line it choked on, which is somebody's page

        self._fetched[link.url] = (self._now(), response.text)
        return document

    def _readable(self, event: Any) -> bool:
        """Whether this event can be expanded, repairing what can be repaired.

        `recurring_ical_events` is asked to skip a series it cannot expand, and it does —
        silently, inside the library. Silently is the problem: a recurring meeting vanishing
        from the page with no trace is the failure the whole connector is arranged against.
        So both times are touched here, where a skip can be said out loud.

        The two are not equally serious. **An unreadable start is fatal to the event** —
        there is nowhere to put it. **An unreadable end is not**: the meeting is still at
        two o'clock, and the honest answer is to drop the end and draw a point in time. So
        the end is removed and the event goes through, rather than the whole thing being
        dropped inside the library for a field the page can live without.
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
        try:
            finishes = event.get('DTEND')
            if finishes is not None:
                _ = finishes.dt
        except Exception as error:  # noqa: BLE001 — same library, same handful of types
            self._log.warning(
                'keeping %r as a point in time: its end cannot be read (%s)',
                str(event.get('SUMMARY') or 'an event with no title'),
                type(error).__name__,
            )
            del event['DTEND']
        return True

    def _calendars(self) -> list[Any]:
        """The calendars to read. Everything, unless somebody named some."""
        if self._principal is None:
            self._principal = self._connect(self._username, self._password).principal()
        every = self._principal.calendars()
        if not self._wanted:
            return every

        # `get_display_name()`, not `.name` — caldav 3.3 deprecated the attribute, and a
        # DeprecationWarning raised mid-way through building a page is not a thing to leave
        # for later. The live test against a real account is what found it.
        by_name = {str(calendar.get_display_name()): calendar for calendar in every}
        for name in self._wanted:
            if name not in by_name:
                self._log.warning('no calendar called %r on this account; skipping it', name)
        return [by_name[name] for name in self._wanted if name in by_name]

    def _name_of(self, calendar: Any) -> str:
        """What to file this calendar's events under.

        A name is what makes colour possible — the page draws Shaun's meetings and the kids'
        school run in different inks, and it has nothing else to tell them apart by. A
        calendar that will not give one still puts its events on the page, in the uncoloured
        grey, because a nameless calendar is a cosmetic problem and a missing afternoon is
        not.
        """
        try:
            name = str(calendar.get_display_name() or '').strip()
        except Exception as error:  # noqa: BLE001 — caldav raises several types here
            self._log.info('a calendar would not give its name (%s)', type(error).__name__)
            name = ''
        if not name:
            # The URL of a calendar *inside the account*, which needs the app password to
            # use. A published link's URL is the credential itself and is never logged —
            # and never reaches here, because `read_links` refuses a link with no label.
            self._log.info(
                'the calendar at %s has no name; its events are filed under %r',
                getattr(calendar, 'url', 'an unknown address'),
                UNNAMED,
            )
            return UNNAMED
        return name

    def _shape(self, occurrence: Any, calendar: str) -> dict | None:
        """One occurrence into the fields the page needs, or None if it has no start."""
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
            'ends': self._ends(occurrence, when),
            'title': _one_line(occurrence.get('SUMMARY')),
            'where': _one_line(occurrence.get('LOCATION')),
            'calendar': calendar,
        }

    def _ends(self, occurrence: Any, starts: dt.date | dt.datetime) -> str | None:
        """When a timed event finishes **today**, as `"HH:MM"`, or None.

        This is what lets the page draw a block as tall as the time it takes. None means
        there is no block to draw, and three ordinary things mean it:

        * an all-day entry, which has no times at all
        * an event saved with a start and nothing else, which is how a reminder-shaped entry
          arrives — the expander gives those an end equal to their start
        * something that runs past midnight, whose end belongs to a different day. Left in,
          a three-day conference draws a block from 00:00 to 09:00 across this morning

        All three are normal, so none of them says anything.

        A `DURATION` instead of a `DTEND` needs nothing here: `recurring_ical_events` resolves
        one into the other while expanding, and `a-duration.ics` is the test that says so
        rather than a branch that would never run.
        """
        finishes = getattr(occurrence.get('DTEND'), 'dt', None)
        if not isinstance(starts, dt.datetime) or not isinstance(finishes, dt.datetime):
            return None
        here, began = finishes.astimezone(self._zone), starts.astimezone(self._zone)
        if here <= began or here.date() != began.date():
            return None
        return here.strftime('%H:%M')

    def _give_up(self, why: str, key: str) -> Unreachable:
        """One line, once a day **per fault**. Never the password, the URL or the response.

        Keyed by what went wrong rather than by the connector. One key for everything would
        let a transient blip at any hour spend the day's budget, and the sentence a person
        can actually act on — *make a new app-specific password* — would never arrive. This
        tool is callable from any session, so that blip is not hypothetical.
        """
        self._log.warning('could not read the calendar: %s', why)
        # 'Calendar', not 'iCloud': this connector reads published links too, and the
        # sentence already names which of them broke.
        self._alert(f'Calendar: {why}', key=key)
        self._principal = None
        return Unreachable(why)


def _one_line(value: Any) -> str:
    """Free text from a calendar, folded onto one line.

    People put newlines in event titles — `'Kids\n School [15:15 - 15:30]'` is a real entry
    from a real account, five times in one week. iCalendar carries it faithfully and it is
    not wrong, but the morning page is a PDF read at arm's length and a one-line row that is
    two lines breaks it.

    Folding, not shortening: every word survives, and a title that was already one line comes
    back character for character.
    """
    return ' '.join(str(value or '').split())


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


def _why_link(error: Exception, label: str) -> str:
    """What to tell somebody about a link that would not load. Never the URL."""
    if isinstance(error, httpx.TimeoutException):
        return f'{label} did not answer within {LINK_TIMEOUT:g}s'
    if isinstance(error, httpx.HTTPStatusError):
        answered = error.response.status_code
        if answered in (401, 403, 404):
            return (
                f'{label} answered {answered} — that link has probably been withdrawn. '
                'Ask whoever publishes that calendar for a fresh link and put it in SUBSCRIBED'
            )
        return f'{label} answered {answered}'
    return f'{label} could not be reached'


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
            links=read_links(str(context.config.get('subscribed') or ''), context.log),
            zone=zone,
            log=context.log,
            alert=context.alert,
        )
    )
