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
import httpx
import icalendar
import pytest
import respx
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
    """One calendar on the account. Only `get_display_name` and `search`, which is all the
    connector uses."""

    def __init__(
        self,
        name: str,
        documents: list[icalendar.Calendar],
        url: str = 'https://p42-caldav.icloud.com/1234567/calendars/home/',
    ) -> None:
        self._name = name
        self._documents = documents
        self.url = url
        self.searched: list[tuple] = []
        self.fails_with: Exception | None = None

    def get_display_name(self) -> str:
        return self._name

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


@pytest.fixture
def as_configured():
    """Harry's logging, as `harry.main` sets it up, put back afterwards."""
    from harry.main import TALKATIVE, configure_logging

    before = {name: logging.getLogger(name).level for name in TALKATIVE}
    configure_logging()
    yield
    for name, level in before.items():
        logging.getLogger(name).setLevel(level)


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

    assert day == [
        {'at': '14:00', 'ends': '15:00', 'title': 'design review', 'where': 'Kortrijksesteenweg 1', 'calendar': 'Home'}
    ]


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

    assert day == [{'at': '09:30', 'ends': '09:45', 'title': 'standup', 'where': 'meeting room', 'calendar': 'Home'}]


def test_the_same_series_is_there_on_every_monday_and_no_other_day(icloud):
    calendar = connector(icloud(documents=('weekly-standup.ics',)))

    assert calendar.on(dt.date(2026, 9, 21))[0]['at'] == '09:30', 'the next Monday'
    assert calendar.on(dt.date(2026, 9, 15)) == [], 'a Tuesday'


def test_an_instance_moved_to_a_new_time_comes_back_once_at_the_new_time(icloud):
    """The override arrives as a separate object. It only suppresses the generated 09:30 if
    the expander sees both together — expand each object alone and you get the standup twice."""
    day = connector(icloud(documents=('weekly-standup.ics', 'moved-instance.ics'))).on(MONDAY)

    assert day == [{'at': '11:00', 'ends': '11:15', 'title': 'standup', 'where': 'meeting room', 'calendar': 'Home'}]


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

    assert day[0] == {'at': 'all day', 'ends': None, 'title': 'Shaun on leave', 'where': '', 'calendar': 'Home'}
    assert day[1]['at'] == '14:00'


def test_a_time_stored_in_utc_reads_as_the_time_in_the_room(icloud):
    day = connector(icloud(documents=('stored-in-utc.ics',))).on(MONDAY)

    assert day == [{'at': '09:30', 'ends': '10:00', 'title': 'dentist', 'where': '', 'calendar': 'Home'}]


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


def test_a_calendars_name_is_read_the_way_caldav_still_supports(icloud, recwarn):
    """caldav 3.3 deprecated `Calendar.name`. Using it worked in every stand-in test and
    raised against a real account, because this repository turns Harry's own deprecation
    warnings into errors — so the first thing that ever exercised the production path was
    the live test, and it went red on the first run.
    """
    import warnings

    account = [StandInCalendar('Home', recorded('afternoon.ics'))]
    built = icloud(calendars=account, settings=f'USERNAME=u\nAPP_PASSWORD={PASSWORD}\nCALENDARS=Home\n')

    with warnings.catch_warnings():
        warnings.simplefilter('error', DeprecationWarning)
        assert [event['title'] for event in connector(built).on(MONDAY)] == ['design review']

    source = (REPO / '.harry' / 'connectors' / 'icloud' / 'connector.py').read_text(encoding='utf-8')
    assert 'calendar.name' not in source, 'the deprecated attribute is back'


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
    assert len(sink.heard) == 1 and sink.heard[0].startswith('Calendar: ')
    assert re.search(why, sink.heard[0]), sink.heard
    assert 'could not read the calendar' in caplog.text


def test_a_refused_password_says_what_to_do_about_it(icloud):
    built = icloud(documents=('afternoon.ics',), fails_with=AuthorizationError('401'))

    with pytest.raises(Exception, match='make a new app-specific password'):
        connector(built).on(MONDAY)

    _, sink = built
    assert sink.heard == ['Calendar: the password was refused — make a new app-specific password at account.apple.com']


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
    assert hasattr(caldav.Calendar, 'get_display_name'), 'caldav renamed the display-name call'
    assert hasattr(StandInCalendar, 'get_display_name'), 'the stand-in does not offer it'
    # The nameless-calendar line prints this so the calendar can be found and named. If
    # caldav renames it the line still prints, saying "an unknown address" — which is
    # exactly the information it exists to carry, and the stand-in would not notice.
    assert hasattr(caldav.Calendar, 'url'), 'caldav renamed the attribute the log line names'
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
        {'at': '09:30', 'ends': '09:45', 'title': 'standup', 'where': 'meeting room', 'calendar': 'Home'},
        {'at': '14:00', 'ends': '15:00', 'title': 'design review', 'where': 'Kortrijksesteenweg 1', 'calendar': 'Home'},
    ]


async def test_claude_asking_with_no_day_gets_today(icloud, tmp_path):
    """The fixtures are all dated 2026-09-14, so today is empty unless it is that Monday —
    which is the honest assertion: no day argument means the day it is now."""
    built = icloud(documents=('afternoon.ics',), tools=(TOOL,))

    answer = await through_mcp(built, tmp_path)

    today = dt.datetime.now(ZoneInfo('Europe/Brussels')).date()
    assert answer.data == (
        [
            {
                'at': '14:00',
                'ends': '15:00',
                'title': 'design review',
                'where': 'Kortrijksesteenweg 1',
                'calendar': 'Home',
            }
        ]
        if today == MONDAY
        else []
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
    assert sink.heard == ['Calendar: iCloud answered something this connector does not understand']


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

    assert calendar._shape(icalendar.Event(), 'Home') is None  # noqa: SLF001 — the guard has no other caller


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


# ---------------------------------------------------------------------------
# A calendar your work publishes
# ---------------------------------------------------------------------------

LINK = 'https://outlook.office365.com/owa/calendar/mailbox/a-secret-segment-nobody-should-see/reachcalendar.ics'
"""The random segment is the whole of a published link's security, so it is planted here
distinctively and asserted to appear nowhere."""


def subscribed(*, label: str = 'KBC Agenda', url: str = LINK) -> str:
    return f'USERNAME=u\nAPP_PASSWORD={PASSWORD}\nSUBSCRIBED={label}={url}\n'


def serving(name: str = 'published-outlook.ics', status: int = 200):
    """Answer a link with a recorded document, or a failure. **Returns the route**, because
    calling `respx.get(...)` a second time registers another one that shadows this — which
    quietly turned a cached body into an empty string once."""
    body = (FIXTURES / name).read_text(encoding='utf-8') if name else ''
    return respx.get(url__startswith='https://outlook.office365.com').mock(
        return_value=httpx.Response(status, text=body, headers={'content-type': 'text/calendar'})
    )


@respx.mock
def test_a_published_links_events_are_in_the_same_day(icloud):
    """One agenda, one day — and every event still says which calendar it came from, because
    the page draws each one in its own colour."""
    serving()
    built = icloud(documents=('afternoon.ics',), settings=subscribed())

    day = connector(built).on(MONDAY)

    assert [event['title'] for event in day] == ['Out of office', 'Sprint planning', 'design review']
    assert day[1] == {
        'at': '09:00',
        'ends': '10:00',
        'title': 'Sprint planning',
        'where': 'Teams',
        'calendar': 'KBC Agenda',
    }


@respx.mock
def test_a_repeating_meeting_from_a_link_lands_on_the_right_day(icloud):
    """The same expansion the iCloud events get. Outlook's own document is what it was
    measured against — 40 of the 234 events in the real one carry an RRULE."""
    serving()
    built = icloud(documents=(), settings=subscribed())

    assert [e['at'] for e in connector(built).on(dt.date(2026, 9, 8)) if e['title'] == 'Weekly sync'] == ['11:00']
    assert [e for e in connector(built).on(dt.date(2026, 9, 9)) if e['title'] == 'Weekly sync'] == []


@respx.mock
def test_an_overridden_instance_from_a_link_appears_once_at_its_new_time(icloud):
    """The real link carries 76 of these. Expanding each object alone would give the meeting
    twice — once at 11:00 and once at 16:00."""
    serving()
    built = icloud(documents=(), settings=subscribed())

    syncs = [e for e in connector(built).on(dt.date(2026, 9, 15)) if e['title'] == 'Weekly sync']

    assert syncs == [
        {'at': '16:00', 'ends': '16:30', 'title': 'Weekly sync', 'where': 'Room 3.14', 'calendar': 'KBC Agenda'}
    ]


@respx.mock
def test_a_multi_day_all_day_block_covers_every_day_of_it(icloud):
    serving()
    built = icloud(documents=(), settings=subscribed())
    calendar = connector(built)

    for day in (dt.date(2026, 9, 14), dt.date(2026, 9, 17), dt.date(2026, 9, 18)):
        assert any(e['title'] == 'Out of office' and e['at'] == 'all day' for e in calendar.on(day)), day
    assert not any(e['title'] == 'Out of office' for e in calendar.on(dt.date(2026, 9, 19)))


@respx.mock
def test_two_links_both_contribute_and_each_is_fetched_once(icloud):
    other = 'https://calendar.google.com/calendar/ical/x/basic.ics'
    outlook = serving()
    elsewhere = respx.get(other).mock(
        return_value=httpx.Response(200, text=(FIXTURES / 'afternoon.ics').read_text(encoding='utf-8'))
    )
    built = icloud(
        documents=(),
        settings=f'USERNAME=u\nAPP_PASSWORD={PASSWORD}\nSUBSCRIBED=KBC Agenda={LINK}|Other=Ω{other}'.replace('Ω', ''),
    )

    day = connector(built).on(MONDAY)

    assert {e['title'] for e in day} == {'Out of office', 'Sprint planning', 'design review'}
    assert outlook.call_count == 1
    assert elsewhere.call_count == 1


@respx.mock
def test_a_link_is_fetched_once_within_five_minutes(icloud):
    """189 KB per call. Asking about a week is seven calls."""
    route = serving()
    built = icloud(documents=(), settings=subscribed())
    calendar = connector(built)
    clock = dt.datetime(2026, 9, 14, 7, 0, tzinfo=dt.timezone.utc)
    calendar._now = lambda: clock  # noqa: SLF001

    for offset in range(4):
        calendar.on(MONDAY + dt.timedelta(days=offset))

    assert route.call_count == 1

    clock = clock + dt.timedelta(minutes=6)
    calendar._now = lambda: clock  # noqa: SLF001
    calendar.on(MONDAY)

    assert route.call_count == 2


@respx.mock
def test_no_links_configured_fetches_nothing(icloud):
    route = serving()
    built = icloud(documents=('afternoon.ics',))

    assert [e['title'] for e in connector(built).on(MONDAY)] == ['design review']
    assert route.call_count == 0


# -- when a link will not load ----------------------------------------------


@pytest.mark.parametrize(
    ('status', 'why'),
    [
        (404, 'KBC Agenda answered 404'),
        (403, 'KBC Agenda answered 403'),
        (500, 'KBC Agenda answered 500'),
    ],
)
@respx.mock
def test_a_link_that_is_down_fails_the_whole_read(icloud, status, why):  # noqa: D103 — see below
    """A day missing your work meetings looks exactly like a quiet day, and you would walk
    into a 09:00. The whole agenda fails instead, so the page says "Agenda unavailable" and
    you go and look at your phone."""
    serving(status=status)
    built = icloud(documents=('afternoon.ics',), settings=subscribed())

    with pytest.raises(Exception, match=why):
        connector(built).on(MONDAY)

    _, sink = built
    assert len(sink.heard) == 1 and why in sink.heard[0]


@respx.mock
def test_a_link_that_cannot_be_reached_at_all_fails_the_whole_read(icloud):
    """A NUC with no DNS at 06:30 is not hypothetical, and this is the sentence that names
    the link — the property the whole no-leak story rests on."""
    respx.get(url__startswith='https://outlook.office365.com').mock(side_effect=httpx.ConnectError('no route'))
    built = icloud(documents=('afternoon.ics',), settings=subscribed())

    with pytest.raises(Exception, match='KBC Agenda could not be reached'):
        connector(built).on(MONDAY)

    _, sink = built
    assert sink.heard == ['Calendar: KBC Agenda could not be reached']


@respx.mock
def test_a_withdrawn_link_says_to_republish_it(icloud):
    serving(status=404)
    built = icloud(documents=(), settings=subscribed())

    with pytest.raises(Exception, match='Ask whoever publishes that calendar'):
        connector(built).on(MONDAY)


@respx.mock
def test_a_link_that_times_out_says_how_long_it_waited(icloud):
    respx.get(url__startswith='https://outlook.office365.com').mock(side_effect=httpx.ReadTimeout('slow'))
    built = icloud(documents=(), settings=subscribed())

    with pytest.raises(Exception, match='KBC Agenda did not answer within 20s'):
        connector(built).on(MONDAY)


@respx.mock
def test_the_link_fetch_carries_the_ceiling_the_message_quotes(icloud):
    """The sentence above says 20 seconds. Asserted on what the request was given, because a
    side-effect timeout raises identically whether or not the connector chose a ceiling —
    and httpx's own default is five, which is short for a 189 KB document."""
    route = serving()
    built = icloud(documents=(), settings=subscribed())

    connector(built).on(MONDAY)

    asked = route.calls.last.request.extensions['timeout']
    assert asked['read'] == 20.0, 'the connector did not choose a ceiling of its own'
    assert asked['connect'] == 20.0


@respx.mock
def test_a_link_answering_a_sign_in_page_says_it_is_not_a_calendar(icloud):
    """An expired published link answers 200 with HTML, not a 404 — which is why this is its
    own case rather than falling out of the status check."""
    serving('not-a-calendar.html')
    built = icloud(documents=(), settings=subscribed())

    with pytest.raises(Exception, match='answered something that is not a calendar'):
        connector(built).on(MONDAY)

    _, sink = built
    assert 'Ask whoever publishes that calendar' in sink.heard[0]


@respx.mock
def test_a_failed_link_is_not_served_from_an_older_success(icloud):
    """An agenda that silently ages is the same lie as a partial one."""
    serving()
    built = icloud(documents=(), settings=subscribed())
    calendar = connector(built)

    assert calendar.on(MONDAY), 'the first read should work'

    calendar._fetched.clear()  # noqa: SLF001 — otherwise the second read never reaches the link
    serving(status=404)
    with pytest.raises(Exception, match='answered 404'):
        calendar.on(MONDAY)


@respx.mock
def test_each_link_gets_its_own_alert_key(icloud):
    """One dead link must not silence a second one that dies an hour later."""
    other = 'https://calendar.google.com/calendar/ical/x/basic.ics'
    respx.get(url__startswith='https://outlook.office365.com').mock(return_value=httpx.Response(404))
    respx.get(other).mock(return_value=httpx.Response(404))
    built = icloud(
        documents=(), settings=f'USERNAME=u\nAPP_PASSWORD={PASSWORD}\nSUBSCRIBED=KBC Agenda={LINK}|Other={other}'
    )
    calendar = connector(built)

    with pytest.raises(Exception, match='KBC Agenda'):
        calendar.on(MONDAY)

    # The first link now fails to resolve at all, so the second is the one that reports.
    respx.get(url__startswith='https://outlook.office365.com').mock(
        return_value=httpx.Response(200, text=(FIXTURES / 'published-outlook.ics').read_text(encoding='utf-8'))
    )
    with pytest.raises(Exception, match='Other'):
        calendar.on(MONDAY)

    _, sink = built
    assert len(sink.heard) == 2, sink.heard
    assert any('KBC Agenda' in line for line in sink.heard) and any('Other' in line for line in sink.heard)


SECRET = 'a-secret-segment-nobody-should-see'


@respx.mock
def test_the_link_reaches_no_log_no_error_and_no_slack(icloud, caplog, as_configured):
    """The random segment in the URL is the password. A link that fails is reported by the
    name a person chose, which is also the thing they can act on.

    Run with Harry's own logging set up, because one half of this is not the connector's:
    **httpx logs every request line, URL included, at INFO**, so `HARRY_LOG_LEVEL=INFO`
    would write the link into the log past a connector that never prints it.
    """
    serving(status=404)
    built = icloud(documents=(), settings=subscribed())

    with caplog.at_level(logging.DEBUG), pytest.raises(Exception) as refused:
        connector(built).on(MONDAY)

    _, sink = built
    assert SECRET not in caplog.text, 'the link reached the log'
    assert SECRET not in str(refused.value), 'the link reached the error'
    assert SECRET not in ' '.join(sink.heard), 'the link reached Slack'


@respx.mock
def test_the_link_is_not_in_the_exception_chain_either(icloud):
    """The half a message check cannot see. httpx puts the request URL inside
    `HTTPStatusError`'s own message, so `raise … from error` hands the credential to
    anything that formats a traceback — and FastMCP does exactly that for a failing tool
    call, at ERROR, whatever `HARRY_LOG_LEVEL` says.

    Asserted over the whole formatted chain rather than `str(error)`, which is the gap that
    let this pass while the property was false.
    """
    import traceback

    serving(status=404)
    built = icloud(documents=(), settings=subscribed())

    with pytest.raises(Exception) as refused:
        connector(built).on(MONDAY)

    whole_chain = ''.join(traceback.format_exception(refused.value))
    assert SECRET not in whole_chain, 'the link is in the traceback anything logging it would print'
    assert refused.value.__cause__ is None, 'the cause carries the URL; raise from None'


@respx.mock
async def test_the_link_does_not_reach_the_log_through_a_failing_tool_call(icloud, tmp_path, caplog, as_configured):
    """Production reaches this through MCP, and MCP is the layer that logs the traceback.
    Calling the connector directly could not have caught the leak this exists for.
    """
    from fastmcp import Client

    from harry.mcp import FIND_TOOLS, build_server
    from harry.store import Store

    serving(status=404)
    catalogue, _ = icloud(documents=(), settings=subscribed(), tools=(TOOL,))

    with caplog.at_level(logging.DEBUG):
        async with Client(build_server(catalogue, Store(tmp_path / 'jobs.json'))) as connected:
            await connected.call_tool(FIND_TOOLS, {'query': 'calendar'})
            result = await connected.call_tool(TOOL, {'day': '2026-09-14'}, raise_on_error=False)

    assert result.is_error is True
    assert SECRET not in str(result.content[0].text)  # type: ignore[union-attr] — an error is one TextContent
    assert SECRET not in caplog.text, 'the link reached the log through the tool call'


@respx.mock
def test_one_unreadable_event_in_a_link_costs_one_event_not_the_day(icloud, caplog):
    """The deliberate exception to "a link failure fails the whole agenda".

    A link that cannot be *reached* tells you nothing about the day, so the read fails. One
    event inside it whose start will not parse is different: the other 233 are right there,
    and failing the morning over one malformed entry would cost the agenda every day until
    somebody at work fixed their calendar. So it is skipped, by name, in the log — the same
    rule the iCloud calendars already follow.
    """
    broken = (
        (FIXTURES / 'published-outlook.ics')
        .read_text(encoding='utf-8')
        .replace(
            'DTSTART;TZID=W. Europe Standard Time:20260914T090000', 'DTSTART;TZID=W. Europe Standard Time:not-a-time'
        )
    )
    respx.get(url__startswith='https://outlook.office365.com').mock(
        return_value=httpx.Response(200, text=broken, headers={'content-type': 'text/calendar'})
    )
    built = icloud(documents=('afternoon.ics',), settings=subscribed())

    with caplog.at_level(logging.WARNING, logger='harry.capability.icloud'):
        day = connector(built).on(MONDAY)

    assert [event['title'] for event in day] == ['Out of office', 'design review'], 'the day should still render'
    assert 'Sprint planning' in caplog.text, 'the dropped event was not named'
    assert 'start time cannot be read' in caplog.text


# -- the setting itself ------------------------------------------------------


@pytest.mark.parametrize(
    ('setting', 'labels'),
    [
        (f'KBC Agenda={LINK}', ['KBC Agenda']),
        (f'KBC Agenda={LINK}|Other=https://x.test/b.ics', ['KBC Agenda', 'Other']),
        ('', []),
        ('   ', []),
    ],
)
def test_subscribed_is_name_equals_url_separated_by_pipes(setting, labels):
    module = __import__('importlib').import_module('harry.loader')  # noqa: F841 — keeps the loader honest
    read_links = _connector_globals()['read_links']

    assert [link.label for link in read_links(setting, logging.getLogger('t'))] == labels


def test_a_url_may_carry_as_many_equals_signs_as_it_likes():
    """Split on the first one. The Outlook links do carry more."""
    awkward = 'https://x.test/cal.ics?a=1&b=2'
    links = _connector_globals()['read_links'](f'Work={awkward}', logging.getLogger('t'))

    assert links[0].url == awkward


@pytest.mark.parametrize('broken', ['not-a-pair', 'Missing url=', '=https://x.test/a.ics', 'Work=ftp://x.test/a.ics'])
def test_a_malformed_subscribed_entry_costs_one_link(broken, caplog):
    with caplog.at_level(logging.WARNING):
        links = _connector_globals()['read_links'](f'{broken}|Good=https://x.test/b.ics', logging.getLogger('t'))

    assert [link.label for link in links] == ['Good']
    assert 'is not Name=https://' in caplog.text


def test_a_malformed_entry_is_reported_by_position_not_by_content(caplog):
    """The content is a credential. Logging the entry to explain the typo would print it."""
    with caplog.at_level(logging.WARNING):
        _connector_globals()['read_links'](f'{LINK}', logging.getLogger('t'))

    assert SECRET not in caplog.text
    assert 'entry 1' in caplog.text


def test_the_link_setting_is_declared_secret_with_no_default():
    """A default on a secret would put a credential in the committed `.env`; `make lint`
    refuses one, and this says why the field looks the way it does."""
    declaration = (REPO / '.harry' / 'connectors' / 'icloud' / 'CONNECTOR.md').read_text(encoding='utf-8')
    block = declaration.partition('subscribed:')[2].partition('timezone:')[0]

    assert 'secret: true' in block
    assert 'default:' not in block

    committed = (REPO / '.harry' / 'connectors' / 'icloud' / '.env').read_text(encoding='utf-8')
    assert 'SUBSCRIBED=\n' in committed, 'the generated .env should carry the key, empty'


def _connector_globals() -> dict:
    """The connector module's namespace, reached through an object the loader built."""
    import shutil

    root = Path(__import__('tempfile').mkdtemp()) / 'root'
    (root / 'connectors').mkdir(parents=True)
    shutil.copytree(REPO / '.harry' / 'connectors' / 'icloud', root / 'connectors' / 'icloud')
    (root / 'connectors' / 'icloud' / '.env.local').write_text(
        f'USERNAME=u\nAPP_PASSWORD={PASSWORD}\n', encoding='utf-8'
    )
    found = load([root]).get('connector', 'icloud')
    assert found is not None and found.target is not None
    return found.target.on.__func__.__globals__


def test_a_broken_link_does_not_tell_the_reader_to_do_somebody_else_s_job():
    """The link this connector was built against is published by an employer. Telling its
    reader to republish the calendar sends them looking for a button that is not theirs —
    and it is the difference between a two-minute fix and an afternoon.

    Read off the shipped source, so a message added later is held to the same rule.
    """
    source = (REPO / '.harry' / 'connectors' / 'icloud' / 'connector.py').read_text(encoding='utf-8')
    sentences = [line for line in source.splitlines() if 'SUBSCRIBED' in line and 'link' in line.lower()]

    assert sentences, 'no message about a broken link — has this moved?'
    for sentence in sentences:
        assert 'epublish' not in sentence, f'only the calendar owner can do that: {sentence.strip()}'


def test_the_docs_say_who_can_reissue_a_published_link():
    """A link you do not own is the one credential here its user cannot rotate, and that is
    the sentence somebody needs *before* they paste one, not after."""
    for page in (REPO / 'docs' / 'sources.md', REPO / '.harry' / 'connectors' / 'icloud' / 'CONNECTOR.md'):
        prose = ' '.join(page.read_text(encoding='utf-8').split())
        assert 'only its owner can do' in prose or 'only the calendar' in prose.lower(), (
            f'{page.name} does not say who can revoke a link'
        )

    operating = ' '.join((REPO / 'docs' / 'operating.md').read_text(encoding='utf-8').split())
    assert 'cannot rotate' in operating or 'may not be able to rotate' in operating, (
        'the runbook does not say which credentials can be rotated'
    )


def test_the_docs_say_the_link_is_a_credential_and_how_to_revoke_it():
    """Republishing in Outlook is the only way to undo a leaked link, and this connector now
    has two hand-renewed credentials rather than one. The page that says how is the
    difference between a two-minute job and an afternoon."""
    for page in (REPO / 'docs' / 'sources.md', REPO / '.harry' / 'connectors' / 'icloud' / 'CONNECTOR.md'):
        prose = ' '.join(page.read_text(encoding='utf-8').split())
        assert 'republish' in prose.lower(), f'{page.name} does not say what revoking a link means'
        assert 'SUBSCRIBED' in prose, f'{page.name} does not name the setting'
        assert 'password' in prose.lower(), f'{page.name} does not say the link is a credential'

    operating = (REPO / 'docs' / 'operating.md').read_text(encoding='utf-8')
    assert 'published calendar link' in operating.lower(), 'the runbook does not list it as a credential'


# ---------------------------------------------------------------------------
# A title that fits on one line
# ---------------------------------------------------------------------------


def test_a_title_with_a_newline_in_it_comes_back_as_one_line(icloud):
    """A real entry from a real account, five times in one week. iCalendar carries the
    newline faithfully; the morning page is a PDF where a one-line row that is two lines
    breaks the row it sits in."""
    day = connector(icloud(documents=('two-line-title.ics',))).on(MONDAY)

    assert day == [
        {
            'at': '15:00',
            'ends': '15:30',
            'title': '👨‍👧‍👦 Kids 🏫 School [15:15 - 15:30]',
            'where': 'Schoolstraat 1 Leuven',
            'calendar': 'Home',
        }
    ]
    assert '\n' not in day[0]['title'] and '\n' not in day[0]['where']


@pytest.mark.parametrize(
    ('given', 'folded'),
    [
        ('Kids\nSchool', 'Kids School'),
        ('Kids\r\nSchool', 'Kids School'),
        ('Kids\tSchool', 'Kids School'),
        ('Kids    School', 'Kids School'),
        ('  Kids School  ', 'Kids School'),
        ('standup', 'standup'),
        ('', ''),
        (None, ''),
    ],
)
def test_free_text_from_a_calendar_is_folded_not_shortened(icloud, given, folded):
    """Every word survives. A title that was already one line comes back character for
    character — this is formatting, not a decision about what matters."""
    one_line = _connector_globals()['_one_line']

    assert one_line(given) == folded


def test_folding_drops_no_word(icloud):
    """The failure to avoid is a fold that quietly becomes a truncation."""
    one_line = _connector_globals()['_one_line']
    given = 'Quarterly planning\nwith the whole team\nand two guests'

    assert one_line(given).split() == given.split()


# ---------------------------------------------------------------------------
# When it ends, and whose calendar it is
# ---------------------------------------------------------------------------


def test_a_timed_event_says_when_it_finishes(icloud):
    """What lets the page draw a block as tall as the time it takes. Without it every
    meeting is a line of text and a two-hour workshop looks like a phone call."""
    day = connector(icloud(documents=('afternoon.ics',))).on(MONDAY)

    assert day[0]['at'] == '14:00'
    assert day[0]['ends'] == '15:00'


def test_an_all_day_event_has_no_end_to_draw(icloud):
    """ "All day" is not a time, so neither is its end. None rather than "23:59", which is a
    time nobody set and would draw a block down the whole column."""
    day = connector(icloud(documents=('all-day.ics', 'afternoon.ics'))).on(MONDAY)

    assert day[0] == {'at': 'all day', 'ends': None, 'title': 'Shaun on leave', 'where': '', 'calendar': 'Home'}


def test_an_event_with_no_end_is_a_point_in_time_not_a_missing_event(icloud):
    """RFC 5545 allows a `DTSTART` alone, and Apple's reminder-shaped entries use it. The
    failure to avoid is the event disappearing from the page."""
    day = connector(icloud(documents=('no-end.ics',))).on(MONDAY)

    assert day == [{'at': '11:30', 'ends': None, 'title': 'call the plumber', 'where': '', 'calendar': 'Home'}]


def test_a_duration_says_when_something_finishes_just_as_an_end_does(icloud):
    """The other half of RFC 5545, and what Google Calendar exports. 17:00 plus PT45M."""
    day = connector(icloud(documents=('a-duration.ics',))).on(MONDAY)

    assert day == [{'at': '17:00', 'ends': '17:45', 'title': 'swimming', 'where': '', 'calendar': 'Home'}]


def test_an_end_that_cannot_be_read_costs_the_block_rather_than_the_event(icloud, caplog):
    """`recurring_ical_events` drops this event entirely, inside the library, saying nothing —
    which is the silence this connector exists to break. The meeting is still at two
    o'clock, so it goes on the page as a point in time and the log says why."""
    built = icloud(documents=('bad-end.ics',))

    with caplog.at_level(logging.WARNING, logger='harry.capability.icloud'):
        day = connector(built).on(MONDAY)

    assert day == [{'at': '14:00', 'ends': None, 'title': 'nonsense end', 'where': '', 'calendar': 'Home'}]
    assert 'as a point in time' in caplog.text
    assert 'nonsense end' in caplog.text


def test_something_that_runs_past_midnight_has_no_end_to_draw_today(icloud):
    """An Exchange-shaped multi-day block starts on a date and ends on a timestamp two days
    later, and the expander turns the pair into a timed event at 00:00. Its end is 09:00 —
    on Wednesday. Printed as this morning's end it draws a block across the school run."""
    day = connector(icloud(documents=('conference.ics',))).on(MONDAY)

    assert day == [{'at': '00:00', 'ends': None, 'title': 'conference', 'where': '', 'calendar': 'Home'}]


def test_every_event_says_which_calendar_it_came_from(icloud):
    """Colour is keyed on this and has nothing else to go on. Two calendars, two names, and
    the merge that used to lose them is gone."""
    built = icloud(
        calendars=[
            StandInCalendar('Shaun', recorded('afternoon.ics')),
            StandInCalendar('Kids', recorded('all-day.ics')),
        ]
    )

    day = connector(built).on(MONDAY)

    assert {event['title']: event['calendar'] for event in day} == {
        'Shaun on leave': 'Kids',
        'design review': 'Shaun',
    }


@respx.mock
def test_a_published_link_files_its_events_under_its_own_label(icloud):
    """The label is what a person reads and the only name that link has — its URL is the
    credential and never leaves the connector."""
    serving()
    built = icloud(documents=('afternoon.ics',), settings=subscribed())

    day = connector(built).on(MONDAY)

    assert {event['calendar'] for event in day} == {'Home', 'KBC Agenda'}


def test_a_calendar_with_no_name_still_puts_its_events_on_the_page(icloud, caplog):
    """A nameless calendar is a cosmetic problem. A missing afternoon is not."""
    built = icloud(calendars=[StandInCalendar('', recorded('afternoon.ics'))])

    with caplog.at_level(logging.INFO, logger='harry.capability.icloud'):
        day = connector(built).on(MONDAY)

    assert [event['calendar'] for event in day] == ['Calendar']
    assert 'has no name' in caplog.text
    assert 'p42-caldav.icloud.com/1234567/calendars/home/' in caplog.text, 'say which one, so it can be named'


def test_the_nameless_line_names_the_calendar_once_per_read(icloud, caplog):
    """Once per read, not once per event. A calendar of forty meetings is one line."""
    built = icloud(calendars=[StandInCalendar('', recorded('afternoon.ics', 'all-day.ics'))])

    with caplog.at_level(logging.INFO, logger='harry.capability.icloud'):
        assert len(connector(built).on(MONDAY)) == 2

    assert len([line for line in caplog.text.splitlines() if 'has no name' in line]) == 1


def test_a_calendar_that_raises_on_its_own_name_is_filed_not_dropped(icloud, caplog):
    """caldav reaches the network for a display name, so this is a request that can fail."""

    class Mute(StandInCalendar):
        def get_display_name(self):
            raise DAVError('the server said no')

    built = icloud(calendars=[Mute('Home', recorded('afternoon.ics'))])

    with caplog.at_level(logging.INFO, logger='harry.capability.icloud'):
        day = connector(built).on(MONDAY)

    assert [event['calendar'] for event in day] == ['Calendar']
    assert 'would not give its name' in caplog.text


@respx.mock
def test_a_published_links_url_is_never_logged_even_when_a_calendar_is_nameless(icloud, caplog):
    """The one URL in this connector that *is* a credential. `read_links` refuses a link
    with no label, so a link can never reach the nameless path — this is the test that says
    so out loud."""
    serving()
    built = icloud(calendars=[StandInCalendar('', recorded('afternoon.ics'))], settings=subscribed())

    with caplog.at_level(logging.DEBUG, logger='harry.capability.icloud'):
        connector(built).on(MONDAY)

    assert 'outlook.office365.com' not in caplog.text
    assert LINK not in caplog.text


async def test_the_end_and_the_calendar_reach_claude(icloud, tmp_path):
    """A field the connector returns and the tool drops is a field nobody can use."""
    built = icloud(documents=('afternoon.ics',), tools=(TOOL,))

    answer = await through_mcp(built, tmp_path, {'day': '2026-09-14'})

    assert answer.data[0]['ends'] == '15:00'
    assert answer.data[0]['calendar'] == 'Home'


def test_the_tool_body_tells_claude_about_the_end_and_the_calendar():
    """The body of a TOOL.md is what Claude reads to choose.

    Phrases only the new paragraphs carry. The bare word "calendar" was already in this file
    three times, in prose about the calendar app, so asserting on it proved nothing.
    """
    prose = ' '.join((REPO / '.harry' / 'tools' / 'icloud_list_events' / 'TOOL.md').read_text(encoding='utf-8').split())

    assert 'whether 14:00 is a phone call or the rest of the afternoon' in prose
    assert 'something that runs past midnight' in prose, 'the third reason `ends` is null'
    assert 'A calendar that will not give its name reads as' in prose
    assert 'the label of a published link' in prose


def test_the_docs_describe_the_end_and_the_calendar():
    """The greppable half of the docs criterion. Whether it reads clearly over coffee is
    inspection, and stays inspection."""
    prose = ' '.join((REPO / 'docs' / 'sources.md').read_text(encoding='utf-8').split())

    assert '"ends": "10:00"' in prose, 'the shape a caller gets'
    assert '"calendar": "Shaun"' in prose
    assert 'something that runs past midnight' in prose, 'the reason `ends` is null most often'
    assert 'a nameless calendar is a cosmetic problem' in prose
