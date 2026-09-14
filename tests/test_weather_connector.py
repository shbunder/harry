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
import shutil
from pathlib import Path

import httpx
import pytest
import respx
from fastmcp import Client

from harry.loader import load
from harry.mcp import FIND_TOOLS, build_server
from harry.store import Store

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
            shutil.copytree(REPO / '.harry' / where, root / where, dirs_exist_ok=True)
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
def test_the_call_asks_for_exactly_the_four_fields_it_reads(weather):
    """`precipitation_probability_max`, not `_mean`. They are different numbers for the same
    day, and the page answers "will I need a coat" — the chance it rains at all."""
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
    ]


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
