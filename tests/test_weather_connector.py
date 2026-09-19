"""The smallest source, and the one that proves the shape.

Loaded, not imported: `pyproject.toml` keeps `.harry` off pytest's path so a test cannot
reach a connector directly and pass while the loader is broken. These copy the real folder
into a temporary root and run it through `load()`.

**No test reaches api.open-meteo.com.** The happy path is a real answer recorded on the
morning this was written; the failures are respx side-effects and two files derived from
that same answer. A suite that reaches the network is a suite that fails on a train.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import httpx
import pytest
import respx
from fastmcp import Client

from harry.loader import load
from harry.mcp import FIND_TOOLS, build_server
from harry.store import Store

from .capability_copy import copy_capability

REPO = Path(__file__).parent.parent
FORECAST = 'https://api.open-meteo.com/v1/forecast'
FIXTURES = Path(__file__).parent / 'fixtures' / 'weather'


def recorded(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding='utf-8'))


@pytest.fixture
def weather(tmp_path, monkeypatch):
    """The real `.harry/connectors/weather/`, loaded, with the tool beside it."""
    for key in ('LATITUDE', 'LONGITUDE', 'TIMEZONE', 'PLACE'):
        monkeypatch.delenv(f'HARRY_WEATHER_{key}', raising=False)

    def build(*, settings: str = '', with_tool: bool = False):
        root = tmp_path / 'root'
        wanted = ['connectors/weather'] + (['tools/weather_forecast'] if with_tool else [])
        for where in wanted:
            (root / where).parent.mkdir(parents=True, exist_ok=True)
            copy_capability(REPO / '.harry' / where, root / where)
        if settings:
            (root / 'connectors' / 'weather' / '.env.local').write_text(settings, encoding='utf-8')
        return load([root])

    return build


def connector(catalogue):
    found = catalogue.get('connector', 'weather')
    assert found is not None and found.target is not None, [f'{c.name}: {c.reason}' for c in catalogue.skipped]
    return found.target


# ---------------------------------------------------------------------------
# The four facts
# ---------------------------------------------------------------------------


@respx.mock
def test_today_is_four_facts_from_one_call(weather):
    """The interface the morning page wrote down before this connector existed."""
    route = respx.get(FORECAST).mock(return_value=httpx.Response(200, json=recorded('leuven-today.json')))

    assert connector(weather()).today() == {'summary': 'overcast', 'high': 22, 'low': 18, 'rain_chance': 59}
    assert route.call_count == 1


@respx.mock
def test_the_call_asks_for_exactly_the_fields_it_reads(weather):
    """`precipitation_probability_max`, not `_mean`. They are different numbers for the same
    day, and the page answers "will I need a coat" — the chance it rains at all.

    `sunrise` and `sunset` ride on the same `daily` list: one call, not two."""
    route = respx.get(FORECAST).mock(return_value=httpx.Response(200, json=recorded('leuven-today.json')))
    connector(weather()).today()

    asked = dict(route.calls[0].request.url.params)
    assert asked['latitude'] == '50.88'
    assert asked['longitude'] == '4.7'
    assert asked['timezone'] == 'Europe/Brussels'
    assert asked['forecast_days'] == '1'
    assert asked['daily'].split(',') == [
        'weather_code',
        'temperature_2m_max',
        'temperature_2m_min',
        'precipitation_probability_max',
        'sunrise',
        'sunset',
    ]
    assert asked['hourly'] == 'temperature_2m,weather_code', 'the shape of the day rides on the same request'


@respx.mock
def test_the_numbers_are_rounded_because_the_page_is_paper(weather):
    """21.5 and 59.0% are noise at arm's length. The recorded answer carries the decimals,
    so this fails if the rounding goes."""
    assert recorded('leuven-today.json')['daily']['temperature_2m_max'] == [21.5]
    respx.get(FORECAST).mock(return_value=httpx.Response(200, json=recorded('leuven-today.json')))

    today = connector(weather()).today()

    assert isinstance(today['high'], int) and today['high'] == 22
    assert isinstance(today['low'], int) and today['low'] == 18


def test_the_call_carries_a_five_second_ceiling(weather, monkeypatch):
    """Asserted on the argument the connector passes, not on the resolved request: httpx's
    own default is five seconds too, so a call with no `timeout=` at all looks identical and
    the assertion would pass whether or not the connector chose anything."""
    passed: dict = {}

    def spy(url, **kwargs):
        passed.update(kwargs)
        return httpx.Response(200, json=recorded('leuven-today.json'), request=httpx.Request('GET', url))

    monkeypatch.setattr(httpx, 'get', spy)
    connector(weather()).today()

    assert passed['timeout'] == 5.0, 'the connector did not choose a ceiling of its own'


# ---------------------------------------------------------------------------
# The words
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ('code', 'word'),
    [
        (0, 'clear'),
        (3, 'overcast'),
        (48, 'fog'),
        (63, 'rain'),
        (75, 'snow'),
        (82, 'showers'),
        (96, 'thunderstorm with hail'),
    ],
)
@respx.mock
def test_a_wmo_code_becomes_the_word_the_table_says(weather, code, word):
    answered = recorded('leuven-today.json')
    answered['daily']['weather_code'] = [code]
    respx.get(FORECAST).mock(return_value=httpx.Response(200, json=answered))

    assert connector(weather()).today()['summary'] == word


@respx.mock
def test_a_code_with_no_word_keeps_the_numbers_and_says_nothing(weather, caplog):
    """A word invented for a condition this table does not know would be neither true nor
    useful. The numbers are both."""
    respx.get(FORECAST).mock(return_value=httpx.Response(200, json=recorded('leuven-unknown-code.json')))

    with caplog.at_level(logging.WARNING, logger='harry.capability.weather'):
        today = connector(weather()).today()

    assert today == {'summary': None, 'high': 22, 'low': 18, 'rain_chance': 59}
    assert 'no word for WMO code 100' in caplog.text


def test_the_table_drops_intensity_on_purpose():
    """ "Moderate rain" and "heavy rain" are the same decision about a coat. Read from the
    connector as the loader loads it, so the table under test is the shipped one."""
    source = (REPO / '.harry' / 'connectors' / 'weather' / 'connector.py').read_text(encoding='utf-8')
    words = source.partition('WORDS = {')[2].partition('}')[0]

    assert words.count("'rain'") == 3, 'slight, moderate and heavy rain are all just rain'
    assert 'moderate' not in words and 'heavy' not in words and 'slight' not in words


# ---------------------------------------------------------------------------
# Nobody knows is an answer
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ('failure', 'why'),
    [
        (httpx.ConnectError('no route to host'), 'could not be reached'),
        (httpx.ReadTimeout('too slow'), 'did not answer within 5s'),
    ],
)
@respx.mock
def test_a_source_that_is_down_is_none_and_a_reason(weather, failure, why, caplog):
    route = respx.get(FORECAST).mock(side_effect=failure)
    client = connector(weather())

    with caplog.at_level(logging.WARNING, logger='harry.capability.weather'):
        assert client.today() is None

    # One attempt. A retry loop here would quietly turn the five-second ceiling into
    # fifteen inside the digest's build, which is the call that already blocks.
    assert route.call_count == 1

    answer = client.forecast()
    assert answer['available'] is False
    assert why in answer['why']
    assert answer['place'] == 'Leuven'
    assert 'no forecast for Leuven' in caplog.text


@respx.mock
def test_a_500_says_which(weather):
    respx.get(FORECAST).mock(return_value=httpx.Response(500, text='upstream is unhappy'))
    client = connector(weather())

    assert client.today() is None
    assert client.forecast()['why'] == 'open-meteo answered 500'


@respx.mock
def test_a_body_with_no_entry_for_today_is_none_rather_than_a_keyerror(weather, caplog):
    """A free endpoint changing shape is a thing that happens, and the failure it must not
    produce is an exception in the middle of building a page."""
    respx.get(FORECAST).mock(return_value=httpx.Response(200, json=recorded('leuven-no-today.json')))
    client = connector(weather())

    with caplog.at_level(logging.WARNING, logger='harry.capability.weather'):
        assert client.today() is None

    assert 'does not understand' in client.forecast()['why']
    assert 'no forecast for Leuven' in caplog.text


@respx.mock
def test_available_is_on_both_answers(weather):
    """So a reader checks one key rather than inferring from which keys are missing."""
    respx.get(FORECAST).mock(return_value=httpx.Response(200, json=recorded('leuven-today.json')))
    assert connector(weather()).forecast()['available'] is True

    respx.get(FORECAST).mock(side_effect=httpx.ConnectError('nope'))
    assert connector(weather()).forecast()['available'] is False


# ---------------------------------------------------------------------------
# Somewhere else
# ---------------------------------------------------------------------------


@respx.mock
def test_somewhere_else_is_a_setting(weather):
    respx.get(FORECAST).mock(return_value=httpx.Response(200, json=recorded('leuven-today.json')))
    catalogue = weather(settings='LATITUDE=51.05\nLONGITUDE=3.72\nPLACE=Ghent\n')

    answer = connector(catalogue).forecast()

    asked = dict(respx.calls[0].request.url.params)
    assert (asked['latitude'], asked['longitude']) == ('51.05', '3.72')
    assert answer['place'] == 'Ghent'


def test_the_committed_env_ships_leuven():
    """A default nobody has to set is one fewer thing between a fresh clone and a working
    page. None of these is a secret, so the committed file carries real values."""
    committed = (REPO / '.harry' / 'connectors' / 'weather' / '.env').read_text(encoding='utf-8')
    values = dict(line.split('=', 1) for line in committed.splitlines() if line and not line.startswith('#'))

    assert values == {'LATITUDE': '50.88', 'LONGITUDE': '4.7', 'TIMEZONE': 'Europe/Brussels', 'PLACE': 'Leuven'}


# ---------------------------------------------------------------------------
# The tool, the way Claude reaches it
# ---------------------------------------------------------------------------


@respx.mock
async def test_claude_can_ask_for_the_forecast(weather, tmp_path):
    respx.get(FORECAST).mock(return_value=httpx.Response(200, json=recorded('leuven-today.json')))
    server = build_server(weather(with_tool=True), Store(tmp_path / 'jobs.json'))

    async with Client(server) as connected:
        assert 'weather_forecast' not in [t.name for t in await connected.list_tools()], 'it should defer'
        found = (await connected.call_tool(FIND_TOOLS, {'query': 'weather'})).data
        assert [row['name'] for row in found['found']] == ['weather_forecast']
        answer = (await connected.call_tool('weather_forecast', {})).data

    assert answer == {
        'available': True,
        'place': 'Leuven',
        'summary': 'overcast',
        'high': 22,
        'low': 18,
        'rain_chance': 59,
        'sunrise': None,
        'sunset': None,
        'hours': [],
    }


@respx.mock
async def test_a_source_that_is_down_reaches_claude_as_an_answer_not_an_error(weather, tmp_path):
    """A tool that raises tells the model it did something wrong, and it did not. The
    forecast nobody can get is information."""
    respx.get(FORECAST).mock(side_effect=httpx.ConnectError('no route to host'))
    server = build_server(weather(with_tool=True), Store(tmp_path / 'jobs.json'))

    async with Client(server) as connected:
        await connected.call_tool(FIND_TOOLS, {'query': 'weather'})
        result = await connected.call_tool('weather_forecast', {}, raise_on_error=False)

    assert result.is_error is False, 'a source being down is an answer, not an error'
    assert result.data == {'available': False, 'place': 'Leuven', 'why': 'open-meteo could not be reached'}


def test_the_tool_imports_the_sdk_and_nothing_else():
    from harry.boundary import forbidden_imports

    assert forbidden_imports(REPO / '.harry' / 'tools' / 'weather_forecast') == []
    assert forbidden_imports(REPO / '.harry' / 'connectors' / 'weather') == []


# ---------------------------------------------------------------------------
# The shape of the day
# ---------------------------------------------------------------------------


@respx.mock
def test_the_forecast_carries_the_day_hour_by_hour(weather):
    """The high alone cannot say whether the warm part is the morning or the evening.

    Against a real answer recorded on 15 September 2026: twenty-four readings, of which the
    eighteen between 06:00 and 23:00 are the ones a person glances at.
    """
    respx.get(FORECAST).mock(return_value=httpx.Response(200, json=recorded('leuven-hourly.json')))

    hours = connector(weather()).forecast()['hours']

    assert [entry['at'] for entry in hours] == [f'{hour:02d}:00' for hour in range(6, 24)]
    assert hours[0] == {'at': '06:00', 'temperature': 17, 'summary': 'clear'}
    # 20.5 at 22:00 in the recording, and Python rounds a half to even — so 20, not 21.
    assert hours[-2] == {'at': '22:00', 'temperature': 20, 'summary': 'overcast'}
    assert hours[-1] == {'at': '23:00', 'temperature': 20, 'summary': 'overcast'}
    assert all(isinstance(entry['temperature'], int) for entry in hours), 'decimals are noise on paper'


@respx.mock
def test_the_small_hours_are_left_off_and_eleven_at_night_is_kept(weather):
    """Twenty-four numbers is a table. The recorded answer carries all of them, so this goes
    red if the window goes — at either end."""
    assert len(recorded('leuven-hourly.json')['hourly']['time']) == 24
    respx.get(FORECAST).mock(return_value=httpx.Response(200, json=recorded('leuven-hourly.json')))

    hours = connector(weather()).forecast()['hours']

    assert len(hours) == 18
    assert '05:00' not in [entry['at'] for entry in hours]
    assert '23:00' in [entry['at'] for entry in hours], 'the late evening is what the strip ends on'


@respx.mock
def test_an_answer_with_no_hourly_block_costs_the_strip_and_nothing_else(weather, caplog):
    """The degraded path, and the reason `_hours` may not raise: the day arrived in the same
    response. `leuven-today.json` is a real answer from before the hourly block was asked
    for, so this is the shape a changed endpoint would produce."""
    assert 'hourly' not in recorded('leuven-today.json')
    respx.get(FORECAST).mock(return_value=httpx.Response(200, json=recorded('leuven-today.json')))

    with caplog.at_level(logging.INFO, logger='harry.capability.weather'):
        answer = connector(weather()).forecast()

    assert answer['available'] is True
    assert (answer['summary'], answer['high'], answer['low'], answer['rain_chance']) == ('overcast', 22, 18, 59)
    assert answer['hours'] == []
    # The only trace a person gets of a strip that quietly stopped arriving, so it is the
    # part a test has to hold. Nothing above INFO: it is not a fault and Slack hears nothing.
    assert 'without its strip' in caplog.text
    assert [record for record in caplog.records if record.levelno > logging.INFO] == []


@respx.mock
def test_an_hour_that_cannot_be_read_drops_out_rather_than_taking_the_panel(weather):
    """A free endpoint changing shape is a thing that happens. One unusable reading must cost
    that reading."""
    broken = recorded('leuven-hourly.json')
    broken['hourly']['temperature_2m'][7] = None
    broken['hourly']['time'][8] = 'not-a-timestamp'
    respx.get(FORECAST).mock(return_value=httpx.Response(200, json=broken))

    hours = connector(weather()).forecast()['hours']

    assert [entry['at'] for entry in hours] == [
        '06:00',
        '09:00',
        '10:00',
        '11:00',
        '12:00',
        '13:00',
        '14:00',
        '15:00',
        '16:00',
        '17:00',
        '18:00',
        '19:00',
        '20:00',
        '21:00',
        '22:00',
        '23:00',
    ]
    assert connector(weather()).forecast()['available'] is True


@respx.mock
def test_two_arrays_of_different_lengths_give_the_part_that_lines_up(weather):
    """Honest beats empty: the readings that have a time keep it."""
    short = recorded('leuven-hourly.json')
    short['hourly']['temperature_2m'] = short['hourly']['temperature_2m'][:10]
    respx.get(FORECAST).mock(return_value=httpx.Response(200, json=short))

    hours = connector(weather()).forecast()['hours']

    assert [entry['at'] for entry in hours] == ['06:00', '07:00', '08:00', '09:00']


@respx.mock
def test_today_stays_four_facts_however_much_the_forecast_carries(weather):
    """`today()` is the narrow answer on purpose. A caller wanting one line should not have to
    carry eighteen temperatures and the sun's times past it."""
    respx.get(FORECAST).mock(return_value=httpx.Response(200, json=recorded('leuven-sun.json')))
    client = connector(weather())

    assert set(client.today()) == {'summary', 'high', 'low', 'rain_chance'}
    assert client.forecast()['sunrise'] == '07:22', 'the forecast does carry it, so today() is choosing'
    assert len(client.forecast()['hours']) == 18


@respx.mock
async def test_the_shape_of_the_day_reaches_claude(weather, tmp_path):
    """A field the connector returns and the tool drops is a field nobody can use."""
    respx.get(FORECAST).mock(return_value=httpx.Response(200, json=recorded('leuven-hourly.json')))
    server = build_server(weather(with_tool=True), Store(tmp_path / 'jobs.json'))

    async with Client(server) as connected:
        await connected.call_tool(FIND_TOOLS, {'query': 'weather'})
        answer = (await connected.call_tool('weather_forecast', {})).data

    assert answer['hours'][0] == {'at': '06:00', 'temperature': 17, 'summary': 'clear'}
    assert len(answer['hours']) == 18


def test_the_docs_describe_the_shape_of_the_day():
    """The greppable half of the docs criterion."""
    prose = ' '.join((REPO / 'docs' / 'sources.md').read_text(encoding='utf-8').split())

    assert 'Eighteen readings, 06:00 to 23:00' in prose
    assert '"at": "06:00", "temperature": 17' in prose
    assert 'loses only the strip' in prose, 'what a missing hourly block costs'


def test_the_fixture_record_lists_the_hourly_answer():
    """A recorded response nobody wrote down is one the next person re-records."""
    record = (REPO / 'tests' / 'fixtures' / 'weather' / 'README.md').read_text(encoding='utf-8')

    assert 'leuven-hourly.json' in record
    assert 'leuven-today.json' in record and 'no `hourly` block' in record


def test_the_tool_body_tells_claude_the_hours_are_there():
    """The body of a TOOL.md is the description Claude reads to choose. A field nobody is
    told about is a field nobody asks for."""
    body = (REPO / '.harry' / 'tools' / 'weather_forecast' / 'TOOL.md').read_text(encoding='utf-8')

    assert 'hours' in body
    assert '06:00' in body and '23:00' in body


@respx.mock
def test_the_day_and_its_hours_read_the_same_table(weather):
    """A 3 must mean "overcast" in both places. Two tables that have to agree is one table
    and a bug, so the hourly word comes from the same `WORDS` the day's does."""
    body = recorded('leuven-hourly.json')
    assert body['daily']['weather_code'] == [3] and 3 in body['hourly']['weather_code']
    respx.get(FORECAST).mock(return_value=httpx.Response(200, json=body))

    answer = connector(weather()).forecast()

    assert answer['summary'] == 'overcast'
    assert {entry['summary'] for entry in answer['hours']} == {'clear', 'overcast'}


@respx.mock
@pytest.mark.parametrize('code', [0, 45, 55, 63, 71, 82, 86, 96])
def test_an_hour_and_its_day_agree_on_every_code_the_table_carries(weather, code):
    """The fixture happens to carry two codes, so a private two-entry table of the hour's own
    would pass every other test in this file. These are codes no recording has — drift on any
    of the twenty-seven and the page says one thing in its panel and another in its strip."""
    body = recorded('leuven-hourly.json')
    body['daily']['weather_code'] = [code]
    body['hourly']['weather_code'] = [code] * 24
    respx.get(FORECAST).mock(return_value=httpx.Response(200, json=body))

    answer = connector(weather()).forecast()

    assert answer['summary'] is not None, 'the table carries this one'
    assert {entry['summary'] for entry in answer['hours']} == {answer['summary']}


@respx.mock
def test_an_hourly_block_with_no_codes_still_draws_the_numbers(weather, caplog):
    """The readings are the part that cannot be guessed from the day's own summary, so losing
    the words must not lose them."""
    body = recorded('leuven-hourly.json')
    del body['hourly']['weather_code']
    respx.get(FORECAST).mock(return_value=httpx.Response(200, json=body))

    with caplog.at_level(logging.INFO, logger='harry.capability.weather'):
        hours = connector(weather()).forecast()['hours']

    assert len(hours) == 18
    assert [entry['summary'] for entry in hours] == [None] * 18
    assert hours[0]['temperature'] == 17
    # The whole day losing its sky must not be quieter than one hour losing it. This is the
    # only trace a person gets of a strip that has been drawing bare numbers for a month.
    assert 'no sky' in caplog.text
    assert '0 code(s) for 24 hour(s)' in caplog.text


@respx.mock
def test_a_code_the_table_does_not_carry_keeps_the_number(weather, caplog):
    """Same rule as the day: the number is still true, and a word invented for a condition
    this table does not know would not be."""
    body = recorded('leuven-hourly.json')
    body['hourly']['weather_code'][6] = 42
    respx.get(FORECAST).mock(return_value=httpx.Response(200, json=body))

    with caplog.at_level(logging.WARNING, logger='harry.capability.weather'):
        hours = connector(weather()).forecast()['hours']

    assert hours[0] == {'at': '06:00', 'temperature': 17, 'summary': None}
    assert '42' in caplog.text


@respx.mock
def test_a_day_of_one_unknown_code_says_so_once_not_eighteen_times(weather, caplog):
    """`_read` warns once because it reads one code. Eighteen hours of the same code is how
    a useful line becomes noise nobody reads."""
    body = recorded('leuven-hourly.json')
    body['hourly']['weather_code'] = [42] * 24
    respx.get(FORECAST).mock(return_value=httpx.Response(200, json=body))

    with caplog.at_level(logging.WARNING, logger='harry.capability.weather'):
        hours = connector(weather()).forecast()['hours']

    assert [entry['summary'] for entry in hours] == [None] * 18
    hourly_lines = [line for line in caplog.text.splitlines() if 'hourly forecast' in line]
    assert len(hourly_lines) == 1
    assert '42' in hourly_lines[0]


@respx.mock
def test_two_unknown_codes_are_both_named_in_the_one_line(weather, caplog):
    """So the line is worth reading: it says which codes to add, not merely that some were
    missing."""
    body = recorded('leuven-hourly.json')
    body['hourly']['weather_code'][6], body['hourly']['weather_code'][7] = 42, 17
    respx.get(FORECAST).mock(return_value=httpx.Response(200, json=body))

    with caplog.at_level(logging.WARNING, logger='harry.capability.weather'):
        connector(weather()).forecast()

    line = next(line for line in caplog.text.splitlines() if 'hourly forecast' in line)
    assert '17, 42' in line


@respx.mock
def test_a_codes_array_shorter_than_the_hours_costs_the_words_not_the_readings(weather, caplog):
    """A malformed answer where one array was truncated. The honest response keeps every
    reading that has a time, and says how many hours lost their word."""
    body = recorded('leuven-hourly.json')
    body['hourly']['weather_code'] = body['hourly']['weather_code'][:8]
    respx.get(FORECAST).mock(return_value=httpx.Response(200, json=body))

    with caplog.at_level(logging.INFO, logger='harry.capability.weather'):
        hours = connector(weather()).forecast()['hours']

    assert len(hours) == 18
    assert [entry['summary'] for entry in hours[:2]] == ['clear', 'clear']
    assert [entry['summary'] for entry in hours[2:]] == [None] * 16
    assert '8 code(s) for 24 hour(s)' in caplog.text


def test_the_docs_and_the_tool_body_describe_the_hourly_sky():
    """A field nobody is told about is a field nobody asks for."""
    prose = ' '.join((REPO / 'docs' / 'sources.md').read_text(encoding='utf-8').split())
    body = ' '.join((REPO / '.harry' / 'tools' / 'weather_forecast' / 'TOOL.md').read_text(encoding='utf-8').split())

    assert '"summary": "clear"' in prose and '"summary": "clear"' in body
    assert "the same WMO table the day's word comes from" in prose
    assert 'once per answer naming every code it could not read' in prose
    assert 'the rain is at the school run or after supper' in body

    runbook = ' '.join(
        (REPO / '.harry' / 'connectors' / 'weather' / 'CONNECTOR.md').read_text(encoding='utf-8').split()
    )
    assert 'An hourly code with no word' in runbook
    assert 'no `weather_code`' in runbook, 'the operator page must name the quiet failure too'


# ---------------------------------------------------------------------------
# The sun
# ---------------------------------------------------------------------------


@respx.mock
def test_the_forecast_says_when_the_sun_rises_and_sets(weather):
    """Against a real answer recorded in Leuven on 19 September 2026, which carried
    `2026-09-19T07:22` and `2026-09-19T19:46`: local time, because the request names a zone."""
    route = respx.get(FORECAST).mock(return_value=httpx.Response(200, json=recorded('leuven-sun.json')))

    answer = connector(weather()).forecast()

    assert (answer['sunrise'], answer['sunset']) == ('07:22', '19:46')
    assert route.call_count == 1, 'the sun rides on the call that already fetches the day'


@respx.mock
def test_an_answer_without_the_sun_keeps_the_forecast(weather, caplog):
    """`leuven-hourly.json` is a real answer from before the sun was asked for. A sunrise
    nobody can read must cost the sunrise — read strictly, like the four facts, it would
    have turned the whole panel into `Weather unavailable`."""
    assert 'sunrise' not in recorded('leuven-hourly.json')['daily']
    respx.get(FORECAST).mock(return_value=httpx.Response(200, json=recorded('leuven-hourly.json')))

    with caplog.at_level(logging.INFO, logger='harry.capability.weather'):
        answer = connector(weather()).forecast()

    assert answer['available'] is True
    assert (answer['summary'], answer['high'], answer['low'], answer['rain_chance']) == ('overcast', 29, 17, 63)
    assert len(answer['hours']) == 18
    assert (answer['sunrise'], answer['sunset']) == (None, None)
    assert 'no sunrise or sunset for Leuven' in caplog.text
    # Not a fault, and Slack hears nothing: weather is the deliberate exception.
    assert [record for record in caplog.records if record.levelno > logging.INFO] == []


@pytest.mark.parametrize(
    'stamps',
    [
        [],
        [None],
        ['07:22'],
        ['2026-09-19T07:22:00'],
        ['2026-09-19T7:22'],
        '2026-09-19T07:22',
        [1726723320],
    ],
    ids=['empty', 'null', 'no-date', 'seconds', 'one-digit-hour', 'not-a-list', 'unixtime'],
)
@respx.mock
def test_a_sunrise_that_cannot_be_read_is_none_and_the_sunset_survives(weather, caplog, stamps):
    """Anything that is not exactly a date and a minute gives no time, rather than one Harry
    guessed at. Each of the two is read on its own."""
    body = recorded('leuven-sun.json')
    body['daily']['sunrise'] = stamps
    respx.get(FORECAST).mock(return_value=httpx.Response(200, json=body))

    with caplog.at_level(logging.INFO, logger='harry.capability.weather'):
        answer = connector(weather()).forecast()

    assert answer['available'] is True
    assert (answer['sunrise'], answer['sunset']) == (None, '19:46')
    assert 'no sunrise for Leuven' in caplog.text


@respx.mock
async def test_the_sun_reaches_claude(weather, tmp_path):
    """A field the connector returns and the tool drops is a field nobody can use."""
    respx.get(FORECAST).mock(return_value=httpx.Response(200, json=recorded('leuven-sun.json')))
    server = build_server(weather(with_tool=True), Store(tmp_path / 'jobs.json'))

    async with Client(server) as connected:
        await connected.call_tool(FIND_TOOLS, {'query': 'weather'})
        answer = (await connected.call_tool('weather_forecast', {})).data

    assert (answer['sunrise'], answer['sunset']) == ('07:22', '19:46')
    assert answer['hours'][-1] == {'at': '23:00', 'temperature': 20, 'summary': 'overcast'}


def test_the_docs_and_the_tool_body_describe_the_sun():
    """The body of a TOOL.md is the description Claude reads to choose. It used to say it was
    not for sunrise, which is now false."""
    body = ' '.join((REPO / '.harry' / 'tools' / 'weather_forecast' / 'TOOL.md').read_text(encoding='utf-8').split())
    prose = ' '.join((REPO / 'docs' / 'sources.md').read_text(encoding='utf-8').split())
    runbook = ' '.join(
        (REPO / '.harry' / 'connectors' / 'weather' / 'CONNECTOR.md').read_text(encoding='utf-8').split()
    )

    assert '"sunrise": "07:22", "sunset": "19:46"' in body
    assert 'or sunrise' not in body
    assert '"sunrise": "07:22", "sunset": "19:46"' in prose
    assert 'No sunrise or sunset in the answer' in runbook
    record = (REPO / 'tests' / 'fixtures' / 'weather' / 'README.md').read_text(encoding='utf-8')
    assert 'leuven-sun.json' in record
    # What Claude reads every morning passes the forecast through whole, so its example should
    # show what arrives.
    candidates = ' '.join(
        (REPO / '.harry' / 'tools' / 'digest_list_candidates' / 'TOOL.md').read_text(encoding='utf-8').split()
    )
    assert '"sunrise": "07:22", "sunset": "19:46"' in candidates
    paper = ' '.join((REPO / 'docs' / 'morning-page.md').read_text(encoding='utf-8').split())
    assert 'when the sun rises and sets, and five hours — 08:00, 12:00, 16:00, 20:00 and 23:00' in paper
