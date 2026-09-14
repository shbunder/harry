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
    class Broken(StandInCalendar):
        def search(self, xml=None, server_expand: bool = False, **searchargs):
            good = Found(recorded('afternoon.ics')[0])
            bad = Found(None)  # type: ignore[arg-type] — walking None is what a bad parse looks like
            return [bad, good]

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
        (Timeout('too slow'), 'iCloud did not answer within 15s'),
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
    assert sink.heard == [f'iCloud: {why}']
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
