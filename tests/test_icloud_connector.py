"""The calendar: one day, expanded here rather than by iCloud.

Loaded, not imported — `pyproject.toml` keeps `.harry` off pytest's path, so these copy the
real folder into a temporary root and run it through `load()`.

**No test here reaches caldav.icloud.com** except the one marked `live`. The rest swap the
connector's own `connect` seam for a stand-in serving the iCalendar documents in
`tests/fixtures/icloud/`, which are handmade — that directory's README says why, and says
what they therefore cannot prove.
"""

from __future__ import annotations

import datetime as dt
import inspect
import logging
import re
import shutil
from pathlib import Path
from zoneinfo import ZoneInfo

import caldav
import icalendar
import pytest
from caldav.lib.error import AuthorizationError, DAVError
from niquests.exceptions import ConnectionError as NiquestsConnectionError, Timeout

from harry.alerts import Alerts
from harry.loader import load

REPO = Path(__file__).parent.parent
FIXTURES = Path(__file__).parent / 'fixtures' / 'icloud'

PASSWORD = 'abcd-efgh-ijkl-never-printed'
"""Planted, and distinctive, so a test can assert it appears nowhere."""

MONDAY = dt.date(2026, 9, 14)
"""Every fixture is dated around it, and it is a Monday, so the weekly series lands on it."""


class Somewhere:
    def __init__(self) -> None:
        self.heard: list[str] = []

    def __call__(self, message: str) -> None:
        self.heard.append(message)


def recorded(*names: str) -> list[icalendar.Calendar]:
    return [icalendar.Calendar.from_ical((FIXTURES / name).read_text(encoding='utf-8')) for name in names]


class Found:
    """What `caldav.Calendar.search` hands back: an object wrapping one iCalendar document."""

    def __init__(self, document: icalendar.Calendar) -> None:
        self.icalendar_instance = document


class StandInCalendar:
    """One calendar on the account. Only `name` and `search`, which is all the connector uses."""

    def __init__(self, name: str, documents: list[icalendar.Calendar]) -> None:
        self.name = name
        self._documents = documents
        self.searched: list[tuple] = []
        self.fails_with: Exception | None = None

    def search(self, xml=None, server_expand: bool = False, **searchargs):
        if self.fails_with is not None:
            raise self.fails_with
        self.searched.append((searchargs.get('start'), searchargs.get('end'), server_expand))
        return [Found(document) for document in self._documents]


class StandInClient:
    """`caldav.DAVClient`, with the network taken out."""

    def __init__(self, calendars: list[StandInCalendar], fails_with: Exception | None = None) -> None:
        self._calendars = calendars
        self._fails_with = fails_with

    def principal(self):
        if self._fails_with is not None:
            raise self._fails_with
        return self

    def calendars(self):
        return self._calendars


@pytest.fixture
def icloud(tmp_path, monkeypatch):
    """The real `.harry/connectors/icloud/`, loaded, with a stand-in for the account."""
    for key in ('USERNAME', 'APP_PASSWORD', 'CALENDARS', 'TIMEZONE'):
        monkeypatch.delenv(f'HARRY_ICLOUD_{key}', raising=False)

    def build(
        *,
        documents: tuple[str, ...] = (),
        calendars: list[StandInCalendar] | None = None,
        settings: str = '',
        fails_with: Exception | None = None,
        tools: tuple[str, ...] = (),
    ):
        root = tmp_path / 'root'
        for where in ('connectors/icloud', *(f'tools/{tool}' for tool in tools)):
            (root / where).parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(REPO / '.harry' / where, root / where, dirs_exist_ok=True)
        configured = settings or f'USERNAME=you@icloud.com\nAPP_PASSWORD={PASSWORD}\n'
        (root / 'connectors' / 'icloud' / '.env.local').write_text(configured, encoding='utf-8')

        alerts = Alerts()
        catalogue = load([root], alerts=alerts)
        alerts.attach(catalogue)
        sink = Somewhere()
        alerts._sinks = [sink]  # noqa: SLF001 — no Slack connector in this root to take them

        found = catalogue.get('connector', 'icloud')
        if found is not None and found.target is not None:
            account = calendars if calendars is not None else [StandInCalendar('Home', recorded(*documents))]
            client = StandInClient(account, fails_with)
            found.target._connect = lambda username, password: client  # noqa: SLF001
        return catalogue, sink

    return build


def connector(built):
    catalogue, _ = built
    found = catalogue.get('connector', 'icloud')
    assert found is not None and found.target is not None, [f'{c.name}: {c.reason}' for c in catalogue.skipped]
    return found.target


# ---------------------------------------------------------------------------
# A day, in order
# ---------------------------------------------------------------------------


def test_a_day_comes_back_as_time_title_and_place(icloud):
    day = connector(icloud(documents=('afternoon.ics',))).on(MONDAY)

    assert day == [{'at': '14:00', 'title': 'design review', 'where': 'Kortrijksesteenweg 1'}]


def test_events_are_earliest_first(icloud):
    day = connector(icloud(documents=('afternoon.ics', 'stored-in-utc.ics'))).on(MONDAY)

    assert [event['at'] for event in day] == ['09:30', '14:00']


def test_a_free_day_is_an_empty_list(icloud):
    """Information, not a failure. The page prints "Nothing on today" from this, and a
    calendar that could not be read raises instead — so the two are never confused."""
    assert connector(icloud(documents=('afternoon.ics',))).on(dt.date(2026, 9, 20)) == []


def test_an_event_with_no_place_says_nothing_rather_than_none(icloud):
    day = connector(icloud(documents=('stored-in-utc.ics',))).on(MONDAY)

    assert day[0]['where'] == ''


# ---------------------------------------------------------------------------
# Recurrence, which iCloud will not do
# ---------------------------------------------------------------------------


def test_a_weekly_event_shows_todays_instance_not_the_series_start(icloud):
    """The whole reason this connector expands recurrences itself. iCloud returns this
    object dated 2026-09-07 when asked for the 14th, and an agenda built on that prints last
    Monday — or drops the meeting, which looks exactly like a cancellation."""
    day = connector(icloud(documents=('weekly-standup.ics',))).on(MONDAY)

    assert day == [{'at': '09:30', 'title': 'standup', 'where': 'meeting room'}]


def test_the_same_series_is_there_on_every_monday_and_no_other_day(icloud):
    calendar = connector(icloud(documents=('weekly-standup.ics',)))

    assert calendar.on(dt.date(2026, 9, 21))[0]['at'] == '09:30', 'the next Monday'
    assert calendar.on(dt.date(2026, 9, 15)) == [], 'a Tuesday'


def test_an_instance_moved_to_a_new_time_comes_back_once_at_the_new_time(icloud):
    """The override arrives as a separate object. It only suppresses the generated 09:30 if
    the expander sees both together — expand each object alone and you get the standup twice."""
    day = connector(icloud(documents=('weekly-standup.ics', 'moved-instance.ics'))).on(MONDAY)

    assert day == [{'at': '11:00', 'title': 'standup', 'where': 'meeting room'}]


def test_a_cancelled_instance_is_not_on_the_page(icloud):
    day = connector(icloud(documents=('cancelled-standup.ics',))).on(MONDAY)

    assert day == []
    assert connector(icloud(documents=('cancelled-standup.ics',))).on(dt.date(2026, 9, 21))[0]['at'] == '09:30'


def test_expand_is_never_asked_for(icloud):
    """iCloud accepts it and ignores it. Passing it would make this code read as though the
    occurrences arriving are somebody else's work."""
    calendar = StandInCalendar('Home', recorded('weekly-standup.ics'))
    connector(icloud(calendars=[calendar])).on(MONDAY)

    assert calendar.searched, 'nothing was searched'
    assert all(expand is False for _, _, expand in calendar.searched)


# ---------------------------------------------------------------------------
# Times and all-day events
# ---------------------------------------------------------------------------


def test_an_all_day_event_says_all_day_and_sorts_first(icloud):
    """Not an empty string, which reads as a missing value, and not 00:00, which is a time
    nobody set."""
    day = connector(icloud(documents=('all-day.ics', 'afternoon.ics'))).on(MONDAY)

    assert day[0] == {'at': 'all day', 'title': 'Shaun on leave', 'where': ''}
    assert day[1]['at'] == '14:00'


def test_a_time_stored_in_utc_reads_as_the_time_in_the_room(icloud):
    day = connector(icloud(documents=('stored-in-utc.ics',))).on(MONDAY)

    assert day == [{'at': '09:30', 'title': 'dentist', 'where': ''}]


def test_a_different_timezone_is_a_setting(icloud):
    built = icloud(
        documents=('stored-in-utc.ics',),
        settings=f'USERNAME=you@icloud.com\nAPP_PASSWORD={PASSWORD}\nTIMEZONE=Asia/Tokyo\n',
    )

    assert connector(built).on(MONDAY)[0]['at'] == '16:30'


def test_a_zone_that_does_not_exist_falls_back_to_utc(icloud, caplog):
    with caplog.at_level(logging.WARNING, logger='harry.capability.icloud'):
        built = icloud(
            documents=('stored-in-utc.ics',),
            settings=f'USERNAME=u\nAPP_PASSWORD={PASSWORD}\nTIMEZONE=Mars/Olympus_Mons\n',
        )

    assert connector(built).on(MONDAY)[0]['at'] == '07:30'
    assert 'no zone called' in caplog.text


def test_today_is_the_day_where_the_page_is_read(icloud):
    """`today()` has to resolve in the configured zone, not the machine's."""
    calendar = connector(icloud(documents=()))
    assert calendar.today() == []


# ---------------------------------------------------------------------------
# Which calendars
# ---------------------------------------------------------------------------


def test_every_calendar_is_read_when_none_is_named(icloud):
    account = [
        StandInCalendar('Home', recorded('afternoon.ics')),
        StandInCalendar('Work', recorded('stored-in-utc.ics')),
    ]

    day = connector(icloud(calendars=account)).on(MONDAY)

    assert [event['title'] for event in day] == ['dentist', 'design review']


def test_naming_calendars_reads_only_those(icloud):
    account = [
        StandInCalendar('Home', recorded('afternoon.ics')),
        StandInCalendar('Work', recorded('stored-in-utc.ics')),
        StandInCalendar('Birthdays', recorded('all-day.ics')),
    ]
    built = icloud(calendars=account, settings=f'USERNAME=u\nAPP_PASSWORD={PASSWORD}\nCALENDARS=Home, Work\n')

    day = connector(built).on(MONDAY)

    assert [event['title'] for event in day] == ['dentist', 'design review']
    assert account[2].searched == [], 'Birthdays should not have been read'


def test_a_calendar_name_that_matches_nothing_is_logged_and_skipped(icloud, caplog):
    """A typo in a setting costs one calendar and a log line, not the agenda."""
    account = [StandInCalendar('Home', recorded('afternoon.ics'))]
    built = icloud(calendars=account, settings=f'USERNAME=u\nAPP_PASSWORD={PASSWORD}\nCALENDARS=Home, Hom\n')

    with caplog.at_level(logging.WARNING, logger='harry.capability.icloud'):
        day = connector(built).on(MONDAY)

    assert [event['title'] for event in day] == ['design review']
    assert "no calendar called 'Hom'" in caplog.text


def test_one_event_that_will_not_parse_costs_one_event(icloud, caplog):
    """`malformed.ics` has a DTSTART that is not a timestamp. It parses at `from_ical` and
    blows up later, at `.dt` — so this is the failure a real bad entry produces, not a
    stand-in returning None.

    Without the guard the whole agenda goes down, and because the exception is neither a
    DAVError nor an OSError it would not even reach the alert: no log, no Slack, no agenda.
    """
    built = icloud(documents=('malformed.ics', 'afternoon.ics'))

    with caplog.at_level(logging.WARNING, logger='harry.capability.icloud'):
        day = connector(built).on(MONDAY)

    assert [event['title'] for event in day] == ['design review'], 'one bad event took the day down'
    assert 'an event nobody can read' in caplog.text, 'it was dropped with no trace'
    assert 'start time cannot be read' in caplog.text


def test_an_object_that_cannot_be_walked_at_all_costs_one_object(icloud, caplog):
    """A different failure from the one above: the document itself is unusable, rather than
    one event inside it."""

    class Broken(StandInCalendar):
        def search(self, xml=None, server_expand: bool = False, **searchargs):
            return [Found(None), Found(recorded('afternoon.ics')[0])]  # type: ignore[arg-type]

    built = icloud(calendars=[Broken('Home', [])])

    with caplog.at_level(logging.WARNING, logger='harry.capability.icloud'):
        day = connector(built).on(MONDAY)

    assert [event['title'] for event in day] == ['design review']
    assert 'would not parse' in caplog.text


# ---------------------------------------------------------------------------
# When it cannot be read
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ('failure', 'why'),
    [
        (Timeout('too slow'), 'iCloud stopped answering .15s per request.'),
        (NiquestsConnectionError('no route to host'), 'iCloud could not be reached'),
        (OSError('the socket went away'), 'iCloud could not be reached'),
        (DAVError('something else'), 'iCloud answered something this connector does not understand'),
    ],
)
def test_a_calendar_that_cannot_be_read_raises_and_says_why(icloud, failure, why, caplog):
    """It raises where weather and news answer, because an empty list already means
    something here: a free day. A dead calendar returning [] would print "Nothing on today"
    on a morning with three meetings in it."""
    built = icloud(documents=('afternoon.ics',), fails_with=failure)

    with caplog.at_level(logging.WARNING, logger='harry.capability.icloud'), pytest.raises(Exception, match=why):
        connector(built).on(MONDAY)

    _, sink = built
    assert len(sink.heard) == 1 and sink.heard[0].startswith('iCloud: ')
    assert re.search(why, sink.heard[0]), sink.heard
    assert 'could not read the calendar' in caplog.text


def test_a_refused_password_says_what_to_do_about_it(icloud):
    built = icloud(documents=('afternoon.ics',), fails_with=AuthorizationError('401'))

    with pytest.raises(Exception, match='make a new app-specific password'):
        connector(built).on(MONDAY)

    _, sink = built
    assert sink.heard == ['iCloud: the password was refused — make a new app-specific password at account.apple.com']


def test_a_calendar_down_all_week_says_so_once_a_day(icloud):
    built = icloud(documents=('afternoon.ics',), fails_with=NiquestsConnectionError('nope'))
    calendar = connector(built)

    for _ in range(3):
        with pytest.raises(Exception, match='could not be reached'):
            calendar.on(MONDAY)

    _, sink = built
    assert len(sink.heard) == 1, 'keyed on the calendar, so a source down all week is one line a day'


def test_the_app_password_reaches_no_log_no_error_and_no_slack(icloud, caplog):
    """Full read access to the calendar, and revoked only by changing the Apple ID
    password. It goes in a gitignored file and comes out nowhere."""
    built = icloud(documents=('afternoon.ics',), fails_with=DAVError(f'rejected Authorization: Basic {PASSWORD}'))

    with caplog.at_level(logging.DEBUG), pytest.raises(Exception) as refused:
        connector(built).on(MONDAY)

    _, sink = built
    assert PASSWORD not in caplog.text, 'the password reached the log'
    assert PASSWORD not in str(refused.value), 'the password reached the error the caller sees'
    assert PASSWORD not in ' '.join(sink.heard), 'the password reached Slack'


def test_no_credential_skips_the_connector_and_says_which_settings(icloud):
    catalogue, _ = icloud(settings='TIMEZONE=Europe/Brussels\n')

    found = catalogue.get('connector', 'icloud')
    assert found is not None and found.target is None
    assert found.reason == 'required settings app_password and username are not set'


def test_nothing_is_dialled_until_a_day_is_asked_for(icloud):
    """A connector that connected at start-up would make Harry's boot wait on Apple's
    slowest surface, and a morning iCloud was down would cost the whole capability."""
    reached: list[str] = []
    catalogue, _ = icloud(documents=('afternoon.ics',))
    found = catalogue.get('connector', 'icloud')
    assert found is not None and found.target is not None
    found.target._connect = lambda username, password: reached.append(username)  # noqa: SLF001

    assert reached == [], 'loading the connector dialled out'


# ---------------------------------------------------------------------------
# A day that is not a date
# ---------------------------------------------------------------------------


@pytest.mark.parametrize('asked', ['tomorrow', '14/09/2026', '2026-13-01', ''])
def test_a_day_that_is_not_a_date_says_the_format_wanted(icloud, asked):
    with pytest.raises(ValueError, match='write it as 2026-09-14'):
        connector(icloud(documents=())).on(asked)


def test_an_iso_string_is_a_day(icloud):
    assert connector(icloud(documents=('afternoon.ics',))).on('2026-09-14')[0]['at'] == '14:00'


# ---------------------------------------------------------------------------
# The stand-in, and the boundary
# ---------------------------------------------------------------------------


def test_the_stand_in_has_the_same_shape_as_the_real_client():
    """Every test above talks to `StandInCalendar`. This is what stops it drifting from
    caldav: the parameters the connector relies on must still be there, with the same names."""
    theirs = inspect.signature(caldav.Calendar.search).parameters  # type: ignore[attr-defined] — caldav types this loosely
    ours = inspect.signature(StandInCalendar.search).parameters

    assert 'server_expand' in theirs, 'caldav renamed the expand argument'
    assert set(ours) <= set(theirs) | {'searchargs'}, 'the stand-in takes something caldav does not'
    for name in ('xml', 'server_expand'):
        assert theirs[name].default == ours[name].default, f'{name} default has drifted'


def test_the_connector_never_writes_to_the_calendar():
    """The password can create, move and delete events. This connector does none of them,
    and the stand-in has no method that would let it."""
    source = (REPO / '.harry' / 'connectors' / 'icloud' / 'connector.py').read_text(encoding='utf-8')

    for forbidden in ('save_event', 'add_event', '.delete(', 'mkcalendar', 'add_todo'):
        assert forbidden not in source, f'{forbidden} is not something Harry does to your calendar'


def test_the_connector_imports_the_sdk_and_nothing_else():
    from harry.boundary import forbidden_imports

    assert forbidden_imports(REPO / '.harry' / 'connectors' / 'icloud') == []
    assert forbidden_imports(REPO / '.harry' / 'tools' / 'icloud_list_events') == []


# ---------------------------------------------------------------------------
# The account itself, which no handmade fixture can vouch for
# ---------------------------------------------------------------------------


@pytest.mark.live
def test_a_real_account_still_answers():
    """The one thing the fixtures cannot prove: that iCloud still behaves the way the spike
    measured, and that the credential works.

    The fixtures in `tests/fixtures/icloud/` are handmade — written against RFC 5545 rather
    than recorded, because there was no account configured when they were written. This is
    what checks the real thing against them.

    Run it deliberately: `make test-live ARGS=tests/test_icloud_connector.py`.
    """
    found = load().get('connector', 'icloud')
    assert found is not None, 'no icloud connector on disk'
    assert found.target is not None, f'not configured: {found.reason}'

    day = found.target.today()

    assert isinstance(day, list)
    for event in day:
        assert set(event) == {'at', 'title', 'where'}, event
        assert event['at'] == 'all day' or len(event['at']) == 5, event['at']


# ---------------------------------------------------------------------------
# The tool, the way Claude reaches it
# ---------------------------------------------------------------------------

TOOL = 'icloud_list_events'


async def through_mcp(built, tmp_path, arguments: dict | None = None, raise_on_error: bool = True):
    """Find the tool the way a session does, then call it."""
    from fastmcp import Client

    from harry.mcp import FIND_TOOLS, build_server
    from harry.store import Store

    catalogue, _ = built
    async with Client(build_server(catalogue, Store(tmp_path / 'jobs.json'))) as connected:
        await connected.call_tool(FIND_TOOLS, {'query': 'calendar'})
        return await connected.call_tool(TOOL, arguments or {}, raise_on_error=raise_on_error)


async def test_the_tool_defers_and_is_found_by_searching_for_a_calendar(icloud, tmp_path):
    """Found by the word a person would use, not by the name of the service."""
    from fastmcp import Client

    from harry.mcp import FIND_TOOLS, build_server
    from harry.store import Store

    catalogue, _ = icloud(documents=('afternoon.ics',), tools=(TOOL,))

    async with Client(build_server(catalogue, Store(tmp_path / 'jobs.json'))) as connected:
        assert TOOL not in [tool.name for tool in await connected.list_tools()], 'it should defer'

        found = (await connected.call_tool(FIND_TOOLS, {'query': 'calendar'})).data
        assert TOOL in [row['name'] for row in found['found']]


async def test_the_tool_is_read_only(icloud, tmp_path):
    """The password can create, move and delete events. This says Harry does not."""
    from fastmcp import Client

    from harry.mcp import FIND_TOOLS, build_server
    from harry.store import Store

    catalogue, _ = icloud(documents=('afternoon.ics',), tools=(TOOL,))

    async with Client(build_server(catalogue, Store(tmp_path / 'jobs.json'))) as connected:
        await connected.call_tool(FIND_TOOLS, {'query': 'calendar'})
        published = {tool.name: tool for tool in await connected.list_tools()}

    hints = published[TOOL].annotations
    assert hints is not None and hints.read_only_hint is True


async def test_claude_can_ask_about_a_named_day(icloud, tmp_path):
    built = icloud(documents=('afternoon.ics', 'weekly-standup.ics'), tools=(TOOL,))

    answer = await through_mcp(built, tmp_path, {'day': '2026-09-14'})

    assert answer.data == [
        {'at': '09:30', 'title': 'standup', 'where': 'meeting room'},
        {'at': '14:00', 'title': 'design review', 'where': 'Kortrijksesteenweg 1'},
    ]


async def test_claude_asking_with_no_day_gets_today(icloud, tmp_path):
    """The fixtures are all dated 2026-09-14, so today is empty unless it is that Monday —
    which is the honest assertion: no day argument means the day it is now."""
    built = icloud(documents=('afternoon.ics',), tools=(TOOL,))

    answer = await through_mcp(built, tmp_path)

    today = dt.datetime.now(ZoneInfo('Europe/Brussels')).date()
    assert answer.data == (
        [{'at': '14:00', 'title': 'design review', 'where': 'Kortrijksesteenweg 1'}] if today == MONDAY else []
    )


@pytest.mark.parametrize('asked', ['tomorrow', '14/09/2026', 'next monday'])
async def test_a_day_that_is_not_a_date_tells_claude_the_format(icloud, tmp_path, asked):
    built = icloud(documents=(), tools=(TOOL,))

    result = await through_mcp(built, tmp_path, {'day': asked}, raise_on_error=False)

    assert result.is_error is True
    assert 'write it as 2026-09-14' in str(result.content[0].text)  # type: ignore[union-attr] — an error is one TextContent


async def test_a_calendar_that_is_down_reaches_claude_as_an_error(icloud, tmp_path):
    """Not an empty day. A source that is down must never be reported as a free morning, and
    an empty list is the answer for a free morning."""
    built = icloud(documents=('afternoon.ics',), tools=(TOOL,), fails_with=NiquestsConnectionError('nope'))

    result = await through_mcp(built, tmp_path, {'day': '2026-09-14'}, raise_on_error=False)

    assert result.is_error is True, 'a dead calendar came back as a free day'
    assert 'could not be reached' in str(result.content[0].text)  # type: ignore[union-attr] — an error is one TextContent


def test_the_tool_is_skipped_when_there_is_no_credential(icloud):
    catalogue, _ = icloud(settings='TIMEZONE=Europe/Brussels\n', tools=(TOOL,))

    found = catalogue.get('tool', TOOL)
    assert found is not None and found.target is None
    assert found.reason == 'needs icloud, which did not load'


def test_the_connector_lists_the_tool_in_provides():
    """Exposure is the connector's choice. CalDAV can walk collections, fetch by UID and run
    raw REPORT queries; none of that is listed here, and that is the point of the list."""
    declaration = (REPO / '.harry' / 'connectors' / 'icloud' / 'CONNECTOR.md').read_text(encoding='utf-8')

    assert 'provides: [icloud_list_events]' in declaration


# ---------------------------------------------------------------------------
# The controls a green suite was not proving
# ---------------------------------------------------------------------------


def test_the_real_client_is_built_with_the_ceiling_the_slack_line_quotes(monkeypatch, icloud):
    """`_reach_icloud` runs only in the live test, so the timeout could be deleted with the
    suite green — while Slack kept saying "15s per request", which would then be a sentence
    about a number nothing applied."""
    passed: dict = {}

    def spy(**kwargs):
        passed.update(kwargs)
        return object()

    module = connector(icloud(documents=())).on.__func__.__globals__
    monkeypatch.setattr(module['caldav'], 'DAVClient', spy)
    module['_reach_icloud']('you@icloud.com', 'a-password')

    assert passed['timeout'] == 15, 'the connector did not choose a ceiling of its own'
    assert passed['url'] == 'https://caldav.icloud.com'


def test_today_is_the_day_in_the_configured_zone_not_the_machines(icloud, monkeypatch):
    """On a container running UTC there is a window every night where the machine's date and
    Brussels' date differ. Kiritimati is UTC+14, so the two disagree for most of the day."""
    built = icloud(documents=(), settings=f'USERNAME=u\nAPP_PASSWORD={PASSWORD}\nTIMEZONE=Pacific/Kiritimati\n')
    calendar = connector(built)

    asked: list[dt.date] = []
    calendar.on = lambda day: asked.append(_a_date_for_test(day))  # type: ignore[assignment] — capture what today() resolved

    calendar.today()

    assert asked == [dt.datetime.now(ZoneInfo('Pacific/Kiritimati')).date()]


def _a_date_for_test(day):
    return day if isinstance(day, dt.date) else dt.date.fromisoformat(str(day))


def test_a_transient_failure_does_not_silence_the_revoked_password(icloud):
    """The sentence a person can act on must not be swallowed by a blip that happened first.

    `icloud_list_events` is callable from any session, so a connection failure at 11am
    burning the day's alert budget is not hypothetical — and the 06:30 agenda would then
    fail with nothing in Slack.
    """
    account = [StandInCalendar('Home', recorded('afternoon.ics'))]
    built = icloud(calendars=account)
    calendar = connector(built)

    account[0].fails_with = NiquestsConnectionError('a blip')
    with pytest.raises(Exception, match='could not be reached'):
        calendar.on(MONDAY)

    account[0].fails_with = AuthorizationError('401')
    with pytest.raises(Exception, match='make a new app-specific password'):
        calendar.on(MONDAY)

    _, sink = built
    assert len(sink.heard) == 2, sink.heard
    assert any('make a new app-specific password' in line for line in sink.heard)


def test_something_neither_dav_nor_os_still_reaches_slack(icloud, caplog):
    """icalendar and lxml both raise types that are neither. Without a final catch the page
    degrades and nobody is told, which is the three-week silence."""

    class Surprising(StandInCalendar):
        def search(self, xml=None, server_expand: bool = False, **searchargs):
            raise RuntimeError('something nobody predicted')

    built = icloud(calendars=[Surprising('Home', [])])

    with (
        caplog.at_level(logging.ERROR, logger='harry.capability.icloud'),
        pytest.raises(Exception, match='does not understand'),
    ):
        connector(built).on(MONDAY)

    _, sink = built
    assert sink.heard == ['iCloud: iCloud answered something this connector does not understand']


def test_a_failure_drops_the_connection_so_the_next_call_builds_a_fresh_one(icloud):
    """The principal is cached after the first successful sign-in, so a connection that dies
    later would be reused forever and a single blip would need a restart to clear.

    The failure has to happen *after* `principal()` succeeds — that is the only state in
    which anything is cached, and so the only state in which the reset does anything. A
    stand-in that fails at sign-in caches nothing and proves nothing.
    """

    class WedgedAfterSignIn(StandInClient):
        def __init__(self) -> None:
            super().__init__([StandInCalendar('Home', recorded('afternoon.ics'))])
            self.dead = True

        def calendars(self):
            if self.dead:
                raise NiquestsConnectionError('the connection went away after sign-in')
            return super().calendars()

    built = icloud(documents=('afternoon.ics',))
    calendar = connector(built)

    wedged = WedgedAfterSignIn()
    healthy = StandInClient([StandInCalendar('Home', recorded('afternoon.ics'))])
    handed: list[StandInClient] = []

    def connect(username, password):
        client = wedged if not handed else healthy
        handed.append(client)
        return client

    calendar._connect = connect  # noqa: SLF001

    with pytest.raises(Exception, match='could not be reached'):
        calendar.on(MONDAY)
    assert handed == [wedged], 'the first call signed in and then broke'

    assert [event['title'] for event in calendar.on(MONDAY)] == ['design review']
    assert handed == [wedged, healthy], 'the dead connection was reused'


def test_reminders_are_never_asked_for(icloud):
    """The most expensive finding this feature made, enforced by nobody having typed
    `todo=True` yet. CalDAV cannot see them — a spike found 14 Apple upgrade placeholders
    across 17 lists — so asking would return placeholders and look like it worked."""
    calendar = StandInCalendar('Home', recorded('afternoon.ics'))
    connector(icloud(calendars=[calendar])).on(MONDAY)

    source = (REPO / '.harry' / 'connectors' / 'icloud' / 'connector.py').read_text(encoding='utf-8')
    assert 'todo=True' not in source and 'VTODO' not in source
    assert 'event=True' in source, 'the search must ask for events specifically'


def test_an_event_with_no_start_is_skipped_rather_than_crashing(icloud):
    """An occurrence with no DTSTART has no time to put on a page, and a KeyError halfway
    through building one is worse than a shorter agenda."""
    calendar = connector(icloud(documents=()))

    assert calendar._shape(icalendar.Event()) is None  # noqa: SLF001 — the guard has no other caller


def test_the_standup_keeps_its_time_across_the_clocks_going_back(icloud):
    """25 October 2026 is when Europe/Brussels leaves summer time. A weekly 09:30 meeting is
    still at 09:30 in November — the wall clock is what a person reads."""
    calendar = connector(icloud(documents=('weekly-standup.ics',)))

    assert calendar.on(dt.date(2026, 10, 19))[0]['at'] == '09:30', 'before the change'
    assert calendar.on(dt.date(2026, 11, 2))[0]['at'] == '09:30', 'after it'


def test_the_docs_say_where_the_password_comes_from_and_what_a_lapse_looks_like():
    """The greppable half of the docs criterion. The other half — whether it reads clearly at
    07:00 to somebody whose agenda just stopped — is inspection, and stays inspection."""
    for page in (REPO / 'docs' / 'sources.md', REPO / '.harry' / 'connectors' / 'icloud' / 'CONNECTOR.md'):
        # Whitespace-normalised: these pages are wrapped at 90 characters, so a phrase that
        # happens to straddle a line break is still the phrase a reader sees.
        prose = ' '.join(page.read_text(encoding='utf-8').split())
        assert 'account.apple.com' in prose, f'{page.name} does not say where the password comes from'
        assert 'App-Specific Passwords' in prose, f'{page.name} does not name the Apple screen'
        assert 'refused' in prose, f'{page.name} does not say what a lapsed password looks like'

    operating = (REPO / 'docs' / 'operating.md').read_text(encoding='utf-8')
    assert 'iCloud app-specific password' in operating, 'the runbook still knows about only one credential'
