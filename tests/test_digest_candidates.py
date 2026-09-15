"""What Claude is handed at 06:30, before anything is chosen.

Loaded, not imported: `pyproject.toml` keeps `.harry` off pytest's path so a test cannot reach
a tool directly and pass while the loader is broken. These copy the real folder into a
temporary root and run it through `load()`.

**No test here reaches a network.** The three connectors are stand-ins steered by a plan file;
what a real one does to the wire is its own suite's business. This file is about what happens
when one of them is missing, or broken, or raises — which is the state this tool exists for.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
from pathlib import Path

import pytest

from harry.loader import load

from .capability_copy import copy_capability

REPO = Path(__file__).parent.parent
TOOL = 'tools/digest_list_candidates'
STANDINS = REPO / 'tests' / 'fixtures' / 'digest' / 'connectors'


@pytest.fixture
def digest(tmp_path, monkeypatch):
    """The real tool, loaded, with whichever stand-ins a test asks for."""

    def build(*, sources: tuple[str, ...] = ('weather', 'icloud', 'news'), **plan):
        root = tmp_path / 'root'
        copy_capability(REPO / '.harry' / TOOL, root / TOOL)
        for name in sources:
            copy_capability(STANDINS / name, root / 'connectors' / name)
        if sources:
            (root / 'connectors' / '_plan.py').write_text(
                (STANDINS / '_plan.py').read_text(encoding='utf-8'), encoding='utf-8'
            )
        where = tmp_path / 'plan.json'
        where.write_text(json.dumps(plan), encoding='utf-8')
        monkeypatch.setenv('HARRY_DIGEST_TEST_PLAN', str(where))
        return load([root])

    return build


def called(catalogue):
    found = catalogue.get('tool', 'digest_list_candidates')
    assert found is not None and found.target is not None, [f'{c.name}: {c.reason}' for c in catalogue.skipped]
    return found.target


def test_one_call_answers_the_weather_the_agenda_and_the_headlines(digest):
    """Three sources, one call. The alternative is three tools to find, three to call and
    three failures to reconcile, before anything has been chosen."""
    answer = called(digest())()

    assert answer['date'] == dt.date.today().isoformat()
    assert answer['weather']['available'] is True and answer['weather']['place'] == 'Leuven'
    assert answer['agenda']['available'] is True
    assert [e['title'] for e in answer['agenda']['events']] == ['standup']
    assert [h['id'] for h in answer['headlines']] == [f'vrt-2026-09-15-story-{n}-and-what-came-of-it' for n in range(3)]
    assert answer['unavailable'] == []


def test_with_no_sources_at_all_it_answers_a_shape_rather_than_an_error(digest):
    """The state this tool ships in, and the one every later source arrives into. A Harry with
    nothing configured must still be askable, or the page cannot be built before the sources
    exist."""
    answer = called(digest(sources=()))()

    assert answer['weather']['available'] is False
    assert answer['agenda']['available'] is False
    assert answer['headlines'] == []
    assert answer['unavailable'] == ['calendar', 'news', 'weather']
    assert 'no weather connector is configured' in answer['weather']['why']


def test_a_source_that_raises_costs_its_own_section_and_nothing_else(digest):
    """One dead source is one section. The whole design rests on this being true of each of
    them separately."""
    answer = called(digest(weather={'raises': 'open-meteo fell over'}))()

    assert answer['weather']['available'] is False
    assert 'open-meteo fell over' in answer['weather']['why']
    assert answer['agenda']['available'] is True, 'the calendar was taken down with it'
    assert len(answer['headlines']) == 3
    assert answer['unavailable'] == ['weather']


def test_every_source_raising_still_answers(digest):
    """Three at once, because a container that has just started has three unconfigured
    sources and one caller expecting an answer."""
    answer = called(
        digest(
            weather={'raises': 'no'},
            icloud={'raises': 'no'},
            news={'raises': 'no'},
        )
    )()

    assert [answer['weather']['available'], answer['agenda']['available']] == [False, False]
    assert answer['headlines'] == []
    assert answer['unavailable'] == ['calendar', 'news', 'weather']


def test_a_raising_source_is_logged_with_what_went_wrong(digest, caplog):
    """The `why` reaches the caller; the log is for whoever is reading the log."""
    built = digest(icloud={'raises': 'the password was refused'})

    with caplog.at_level(logging.WARNING, logger='harry.capability.digest_list_candidates'):
        called(built)()

    assert 'calendar could not answer' in caplog.text
    assert 'the password was refused' in caplog.text


def test_a_dead_feed_the_news_connector_names_is_in_the_same_list(digest):
    """`unavailable` is one list a caller checks, not two. A feed that is down makes the
    headline list shorter and nothing else — it looks exactly like a quiet news day."""
    answer = called(digest(news={'unavailable': [{'source': 'De Tijd', 'why': 'a 404'}]}))()

    assert answer['unavailable'] == ['De Tijd']
    assert len(answer['headlines']) == 3, 'the feeds that did answer are untouched'


def test_headlines_are_capped_and_the_answer_says_how_many_were_dropped(digest):
    """A short list that does not say it is short is a lie of omission."""
    answer = called(digest(news={'many': 50}))(limit=10)

    assert len(answer['headlines']) == 10
    assert answer['dropped'] == 40


def test_nothing_is_dropped_when_everything_fits(digest):
    answer = called(digest(news={'many': 3}))(limit=40)

    assert answer['dropped'] == 0


def test_the_limit_has_a_ceiling_and_a_floor(digest):
    """Sixty is headroom for a caller that wants to filter afterwards; past that it is a
    different tool. Zero or less is a mistake rather than a request."""
    lots = called(digest(news={'many': 200}))(limit=500)
    one = called(digest(news={'many': 200}))(limit=0)

    assert len(lots['headlines']) == 60
    assert len(one['headlines']) == 1


def test_detail_is_passed_through_to_the_source(digest):
    """Harry does not truncate anything itself — `summary` is the feed's own words, and how
    much of them arrive is the news connector's own rule."""
    built = digest(news={'many': 2})
    called(built)(detail='full')

    news = built.get('connector', 'news')
    assert news is not None and news.target is not None
    assert news.target.asked[-1]['detail'] == 'full'


def test_each_source_is_asked_exactly_once(digest):
    """Three calls, not three per section. The morning page is the one call that blocks."""
    built = digest()
    called(built)()

    for name in ('weather', 'icloud'):
        found = built.get('connector', name)
        assert found is not None and found.target is not None
        assert found.target.asked == 1, f'{name} was asked {found.target.asked} times'
    news = built.get('connector', 'news')
    assert news is not None and news.target is not None and len(news.target.asked) == 1


def test_the_tool_loads_with_one_source_missing(digest):
    """`optional:` is what makes this true, and this is the reason it exists."""
    answer = called(digest(sources=('news',)))()

    assert answer['weather']['available'] is False
    assert answer['agenda']['available'] is False
    assert len(answer['headlines']) == 3
    assert answer['unavailable'] == ['calendar', 'weather']


def test_the_tool_body_tells_claude_to_read_it_all_before_choosing():
    """The body of a TOOL.md is the description Claude reads to choose."""
    body = ' '.join((REPO / '.harry' / TOOL / 'TOOL.md').read_text(encoding='utf-8').split())

    assert 'Reach for this first, every morning' in body
    assert 'Nothing here is chosen, ranked or summarised' in body
    assert 'If `unavailable` has an entry, say so' in body, 'the thing a short list looks like'


def test_a_source_that_reports_its_own_failure_is_not_called_available(digest):
    """The weather connector never raises. It catches its own HTTP errors and answers
    `{'available': False, 'why': …}`, because a forecast nobody can get is an answer.

    Forcing `True` over that read as a working forecast with no numbers in it and left
    `unavailable` empty — so the tool told Claude nothing was wrong on a morning open-meteo
    was down, and the intro would have been written about a forecast that was not there.
    """
    answer = called(
        digest(
            weather={'answer': {'available': False, 'place': 'Leuven', 'why': 'open-meteo did not answer within 5s'}}
        )
    )()

    assert answer['weather']['available'] is False
    assert answer['weather']['why'] == 'open-meteo did not answer within 5s'
    assert answer['unavailable'] == ['weather'], 'and the caller is told to say so'


def test_a_source_reporting_its_own_failure_is_logged_too(digest, caplog):
    import logging

    built = digest(weather={'answer': {'available': False, 'why': 'open-meteo answered 503'}})
    with caplog.at_level(logging.WARNING, logger='harry.capability.digest_list_candidates'):
        called(built)()

    assert 'weather says it could not answer' in caplog.text
    assert 'open-meteo answered 503' in caplog.text
