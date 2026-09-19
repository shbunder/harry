"""The morning page, built from what Claude chose.

Loaded, not imported: `pyproject.toml` keeps `.harry` off pytest's path, so a test cannot
reach the tool directly and pass while the loader is broken.

**No test here reaches a network.** The connectors are stand-ins steered by a plan file, and
the one picture a test uses is served by respx. What matters here is the shape of the paper —
what goes where, in which order, and what happens when a piece of it is missing.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
import pytest
import respx
from pypdf import PdfReader

from harry.loader import load

from .capability_copy import copy_capability

REPO = Path(__file__).parent.parent
TOOL = 'tools/digest_build'
STANDINS = REPO / 'tests' / 'fixtures' / 'digest' / 'connectors'

A_PIXEL = bytes.fromhex(
    '89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4'
    '890000000a49444154789c6360000002000100ffff03000006000557bfabd400'
    '00000049454e44ae426082'
)


@pytest.fixture
def digest(tmp_path, monkeypatch):
    """The real tool, loaded, with whichever stand-ins a test asks for."""

    def build(*, sources=('weather', 'icloud', 'news'), settings: str = '', **plan):
        root = tmp_path / 'root'
        copy_capability(REPO / '.harry' / TOOL, root / TOOL)
        for name in sources:
            copy_capability(STANDINS / name, root / 'connectors' / name)
        if sources:
            (root / 'connectors' / '_plan.py').write_text(
                (STANDINS / '_plan.py').read_text(encoding='utf-8'), encoding='utf-8'
            )
        (root / TOOL / '.env.local').write_text(f'OUT_DIR={tmp_path / "out"}\n{settings}\n', encoding='utf-8')
        where = tmp_path / 'plan.json'
        where.write_text(json.dumps(plan), encoding='utf-8')
        monkeypatch.setenv('HARRY_DIGEST_TEST_PLAN', str(where))
        return load([root])

    return build


def inside(catalogue, name: str):
    """One function out of the loaded tool, rather than out of an import.

    `pyproject.toml` keeps `.harry` off the path on purpose: a test that imports a capability
    directly can pass while the loader is broken. So the few unit-level things here are dug
    out of the module the loader actually built — `digest_build`'s own globals, and the page
    module it imported.
    """
    tool = built(catalogue).__globals__
    page = tool['fit'].__globals__
    drawing = page['timetable'].__globals__
    return {**drawing, **page, **tool}[name]


def built(catalogue):
    found = catalogue.get('tool', 'digest_build')
    assert found is not None and found.target is not None, [f'{c.name}: {c.reason}' for c in catalogue.skipped]
    return found.target


def pick(n: int, **rest) -> dict:
    return {
        'id': f'vrt-2026-09-15-story-{n}-and-what-came-of-it',
        'note': f'Why story {n} matters.',
        'topic': 'belgium',
        **rest,
    }


def today() -> str:
    """What the page will be called, on the clock the tool actually reads.

    `tool.py` takes `dt.datetime.now(zone).date()` in the digest's own timezone, so a
    literal date here is an assertion that passes until midnight and then reports a bug
    that is not there. It did: this test was written on the 15th and went red at 00:04 on
    the 16th, on `['2026-09-16'] == ['2026-09-15']`.

    The property is "named for today where the page is read", not "named 2026-09-15".
    """
    return dt.datetime.now(ZoneInfo('Europe/Brussels')).date().isoformat()


def text_of(path: str) -> str:
    """Every page's text as one line.

    Whitespace-normalised: a heading wraps mid-phrase in the PDF, so `AI and technology`
    comes back with a newline in the middle of it and an `in` check on the raw text is a
    coin toss.
    """
    return ' '.join(' '.join((page.extract_text() or '').split()) for page in PdfReader(path).pages)


def says(prose: str, phrase: str) -> bool:
    """Whether the page carries this phrase, ignoring spacing.

    A section heading is set with 0.2em of tracking, which makes WeasyPrint emit every glyph
    separately — so `AI and technology` reads back as `A I A N D T E C H N O L O G Y`. That is
    the page being right and the extraction being literal, so the comparison drops spaces
    rather than the design dropping the tracking.
    """
    return phrase.replace(' ', '').casefold() in prose.replace(' ', '').casefold()


def test_a_page_is_built_and_says_what_it_is(digest):
    """The answer is what a caller has to act on: where the file is, how big it came out, and
    whether either sheet ran over."""
    answer = built(digest(news={'many': 8}))(intro='A quiet Tuesday.', picks=[pick(0), pick(1)])

    assert answer['page']['size'] == [509.34, 679.13], 'the tablet rescales anything else'
    assert answer['page']['pages'] >= 3, 'a front sheet and a page per story'
    assert answer['page']['crowded'] == []
    assert answer['front'] == 2 and answer['more'] == 0
    assert Path(answer['page']['path']).is_file()


def test_the_intro_and_every_note_reach_the_page_unedited(digest):
    """Harry never rewrites either. Editing them would be reasoning about what Claude meant,
    and Claude is right there."""
    answer = built(digest(news={'many': 4}))(
        intro='A full Tuesday: the school run at seven.',
        picks=[
            {
                'id': 'vrt-2026-09-15-story-0-and-what-came-of-it',
                'note': 'Worth ten minutes on the train.',
                'topic': 'world',
            }
        ],
    )

    prose = text_of(answer['page']['path'])
    assert 'A full Tuesday: the school run at seven.' in prose
    assert 'Worth ten minutes on the train.' in prose


def test_the_paper_runs_in_the_readers_order_whatever_order_it_was_handed(digest):
    """Home, abroad, technology, culture, sport, and the one worth knowing. The topic is not
    decoration, it is the running order — so a caller may hand them over in any order."""
    answer = built(digest(news={'many': 6}))(
        intro='Ordered.',
        picks=[
            {'id': 'vrt-2026-09-15-story-0-and-what-came-of-it', 'note': 'An oddity.', 'topic': 'oddity'},
            {'id': 'vrt-2026-09-15-story-1-and-what-came-of-it', 'note': 'Abroad.', 'topic': 'world'},
            {'id': 'vrt-2026-09-15-story-2-and-what-came-of-it', 'note': 'At home.', 'topic': 'belgium'},
        ],
    )

    prose = text_of(answer['page']['path'])
    assert prose.index('At home.') < prose.index('Abroad.') < prose.index('An oddity.')


def test_a_second_sheet_carries_the_rest_grouped_by_subject(digest):
    """Six on the front and everything else at a glance, under its own heading."""
    answer = built(digest(news={'many': 10}))(
        intro='Two sheets.',
        picks=[pick(0)],
        more=[
            {'id': 'vrt-2026-09-15-story-1-and-what-came-of-it', 'topic': 'tech'},
            {'id': 'vrt-2026-09-15-story-2-and-what-came-of-it', 'topic': 'culture'},
        ],
    )

    prose = text_of(answer['page']['path'])
    assert says(prose, 'Also today')
    assert says(prose, 'AI and technology') and says(prose, 'Culture')
    assert not says(prose, 'Basketball'), 'a section with nothing in it is not drawn'
    assert answer['more'] == 2


def test_a_companion_piece_gets_its_own_page(digest):
    """A "see also" you cannot open is a headline, and the tablet has no address bar."""
    answer = built(digest(news={'many': 4}))(
        intro='Grouped.',
        picks=[
            {
                'id': 'vrt-2026-09-15-story-0-and-what-came-of-it',
                'note': 'The lead.',
                'topic': 'world',
                'also': ['vrt-2026-09-15-story-1-and-what-came-of-it'],
            }
        ],
    )

    assert answer['articles'] == 2, 'the lead and its companion'
    assert says(text_of(answer['page']['path']), 'Part of')


def test_an_id_that_lost_its_last_word_still_finds_its_story(digest):
    """Measured twice on Haiku against a real morning, in both directions. Prose did not fix
    it, so this does — and says so, because a silent correction is how the wrong story gets
    printed and nobody finds out."""
    answer = built(digest(news={'many': 4}))(intro='Mended.', picks=[pick(0, id='vrt-2026-09-15-story-0')])

    assert answer['resolved'] == [
        {'asked': 'vrt-2026-09-15-story-0', 'used': 'vrt-2026-09-15-story-0-and-what-came-of-it'}
    ]


def test_an_id_that_gained_a_word_finds_it_too(digest):
    """The second run's failure: rebuilt from the headline and longer than the real thing."""
    answer = built(digest(news={'many': 4}))(
        intro='Mended.', picks=[pick(0, id='vrt-2026-09-15-story-0-and-what-came-of-it-over-de-woningmarkt')]
    )

    assert answer['resolved'][0]['used'] == 'vrt-2026-09-15-story-0-and-what-came-of-it'


def test_an_id_that_could_mean_two_things_is_refused(digest):
    """Ambiguity is refused rather than guessed. `story-1` begins `story-1` and nothing else,
    but a bare `vrt-2026-09-15-story` with twelve candidates behind it means any of them."""
    with pytest.raises(Exception, match='could mean any of'):
        built(digest(news={'many': 12}))(intro='Ambiguous.', picks=[pick(0, id='vrt-2026-09-15-story')])


def test_an_id_no_candidate_matches_names_itself(digest):
    with pytest.raises(Exception, match='no candidate is'):
        built(digest(news={'many': 4}))(intro='Unknown.', picks=[pick(0, id='bbc-2026-09-15-never-happened')])


def test_a_story_whose_text_will_not_come_still_earns_its_page(digest):
    """Claude chose it, and the feed's own summary is real reporting. A blank page throws
    away both."""
    answer = built(digest(news={'many': 4, 'unreadable': ['vrt-2026-09-15-story-0-and-what-came-of-it']}))(
        intro='Blocked.', picks=[pick(0)]
    )

    prose = text_of(answer['page']['path'])
    assert 'Full text unavailable' in prose
    assert 'it answered 403' in prose
    assert 'Why story 0 matters.' in prose, 'the note survives'


def test_no_weather_connector_costs_the_panel_and_not_the_page(digest):
    answer = built(digest(sources=('news',)))(intro='No sky.', picks=[pick(0)])

    assert answer['page']['crowded'] == []
    assert answer['page']['pages'] >= 2


def test_a_calendar_that_raises_costs_the_column_and_not_the_page(digest, caplog):
    """A lapsed password is the case this is really about, and it must not take the news
    with it."""
    import logging

    built_now = digest(icloud={'raises': 'the password was refused'}, news={'many': 4})
    with caplog.at_level(logging.WARNING, logger='harry.capability.digest_build'):
        answer = built(built_now)(intro='No agenda.', picks=[pick(0)])

    assert 'no agenda on the page' in caplog.text
    assert 'Why story 0 matters.' in text_of(answer['page']['path'])


def test_with_no_tablet_the_page_is_still_on_disk_and_the_answer_says_so(digest):
    """`make digest-dry` is this path, and so is a morning when the token has lapsed."""
    answer = built(digest(news={'many': 4}))(intro='On disk.', picks=[pick(0)])

    assert answer['delivered'] == {'pushed': False, 'why': 'no tablet connector is configured'}
    assert Path(answer['page']['path']).is_file()


def test_with_a_tablet_the_page_is_pushed_and_still_on_disk(digest):
    """A push is a copy, not a move."""
    catalogue = digest(sources=('weather', 'icloud', 'news', 'remarkable'), news={'many': 4})
    answer = built(catalogue)(intro='Delivered.', picks=[pick(0)])

    assert answer['delivered']['pushed'] is True
    assert answer['delivered']['name'] == answer['page']['path'].split('/')[-1].removesuffix('.pdf')
    assert Path(answer['page']['path']).is_file()
    tablet = catalogue.get('connector', 'remarkable')
    assert tablet is not None and tablet.target is not None and len(tablet.target.pushed) == 1


def test_an_empty_picks_list_is_refused(digest):
    with pytest.raises(Exception, match='picks is empty'):
        built(digest(news={'many': 4}))(intro='Nothing.', picks=[])


def test_too_many_picks_are_refused_rather_than_rendered(digest):
    """An uncapped picks list is an uncapped PDF at one to two pages each."""
    with pytest.raises(Exception, match='more than the 12'):
        built(digest(news={'many': 20}))(intro='Too many.', picks=[pick(n) for n in range(13)])


def test_too_many_second_page_stories_are_refused(digest):
    with pytest.raises(Exception, match='more than the 20'):
        built(digest(news={'many': 30}))(
            intro='Too many.',
            picks=[pick(0)],
            more=[{'id': f'vrt-2026-09-15-story-{n}-and-what-came-of-it', 'topic': 'belgium'} for n in range(1, 22)],
        )


@respx.mock
def test_a_picture_that_will_not_come_costs_the_picture(digest):
    """Nothing is retried beyond the one browser User-Agent, and nothing is said: a feed that
    publishes no pictures is a feed, not a fault."""
    respx.get('https://pictures.test/0.jpg').mock(return_value=httpx.Response(404))
    answer = built(digest(news={'many': 4, 'image': 'https://pictures.test/0.jpg'}))(
        intro='No picture.', picks=[pick(0)]
    )

    assert 'Why story 0 matters.' in text_of(answer['page']['path'])
    assert answer['page']['crowded'] == []


@respx.mock
def test_a_picture_is_fetched_with_a_browser_user_agent(digest):
    """`images.tijd.be` answers 403 to a plain request and 200 to a browser. Measured — the
    picture was silently missing from every De Tijd story until that header."""
    route = respx.get('https://pictures.test/0.jpg').mock(
        return_value=httpx.Response(200, content=A_PIXEL, headers={'content-type': 'image/png'})
    )
    built(digest(news={'many': 4, 'image': 'https://pictures.test/0.jpg'}))(intro='A picture.', picks=[pick(0)])

    assert route.called
    assert 'Mozilla' in route.calls[0].request.headers['user-agent']


def test_the_tool_body_says_the_topic_is_the_running_order():
    """The body of a TOOL.md is the description Claude reads to choose."""
    body = ' '.join((REPO / '.harry' / TOOL / 'TOOL.md').read_text(encoding='utf-8').split())

    assert 'the topic is not decoration, it is the running order' in body
    assert 'Nothing here is chosen, rewritten or summarised' in body
    assert 'replaces the first on the tablet' in body


def test_deliver_false_writes_the_page_and_stops(digest):
    """`make digest-dry` is this, and it is the only reason to pass it. A machine with a token
    would otherwise push every time somebody wanted to see whether the page looked right."""
    catalogue = digest(sources=('weather', 'icloud', 'news', 'remarkable'), news={'many': 4})
    answer = built(catalogue)(intro='Dry.', picks=[pick(0)], deliver=False)

    assert answer['delivered'] == {'pushed': False, 'why': 'deliver=false — the page is on disk only'}
    assert Path(answer['page']['path']).is_file()
    tablet = catalogue.get('connector', 'remarkable')
    assert tablet is not None and tablet.target is not None and tablet.target.pushed == []


def test_the_make_targets_name_a_tool_rather_than_a_module():
    """`make digest-now` pointed at `harry.modules.digest`, which never existed — and the
    module it named would have put a capability's name inside core. The recipes name a tool
    and go through `scripts/call_tool.py`, which knows about no capability at all."""
    recipes = (REPO / 'Makefile').read_text(encoding='utf-8')

    assert 'harry.modules.digest' not in recipes, 'a module that never existed'
    assert 'digest-now:' not in recipes, 'pushing belongs to the tool, behind deliver'
    assert 'scripts/call_tool.py digest_list_candidates' in recipes
    assert 'scripts/call_tool.py digest_build' in recipes
    assert '"deliver"]=False' in recipes, 'digest-dry must not push from a machine with a token'


def test_call_tool_knows_no_capability_by_name():
    """The whole reason it is generic: `make digest-dry` naming a tool in a recipe is a
    developer convenience, and the script that runs it learns no capability's name.

    The **code**, not the prose. Its docstrings give `digest_build` as the usage example and
    say why the script is generic, which is exactly where a name belongs — a guard that
    banned it from the comments too would be a guard that banned explaining the rule.
    """
    import ast

    tree = ast.parse((REPO / 'scripts' / 'call_tool.py').read_text(encoding='utf-8'))
    for node in ast.walk(tree):
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            node.value.value = ''  # a docstring or a bare string
    code = ast.unparse(tree)

    for name in ('digest', 'weather', 'icloud', 'news', 'remarkable', 'slack'):
        assert name not in code, f'{name} is named in the code of call_tool.py'


def test_the_docs_say_what_a_reader_sets_and_what_breaks_quietly():
    """The page a person opens when the paper looks wrong, or when they want to change its
    name. Five settings and one silence worth naming."""
    prose = ' '.join((REPO / 'docs' / 'morning-page.md').read_text(encoding='utf-8').split())
    index = (REPO / 'docs' / 'index.md').read_text(encoding='utf-8')

    assert 'morning-page.md' in index, 'a page nobody links to is a page nobody reads'
    for setting in ('NAME', 'COLOURS', 'FOLDER', 'OUT_DIR', 'TIMEZONE'):
        assert setting in prose, f'{setting} is not documented'
    assert 'make digest-dry PICKS=picks.json' in prose
    assert 'morning-page has not run today' in prose, 'the one failure with no other trace'
    assert 'the columns are local' in prose
    assert 'silent correction is how the wrong story gets printed' in prose


def test_a_push_that_fails_leaves_the_page_and_says_where_it_is(digest, caplog):
    """A push that failed must not take the answer down with it. The page is rendered and on
    disk by now; raising loses the path — and the brief tells Claude to call `digest_build`
    once more on an error, which would re-fetch every article and re-render the whole PDF at
    06:30 for a tablet that is merely offline."""
    import logging

    catalogue = digest(
        sources=('weather', 'icloud', 'news', 'remarkable'),
        news={'many': 4},
        remarkable={'raises': 'the tablet could not be reached'},
    )
    with caplog.at_level(logging.WARNING, logger='harry.capability.digest_build'):
        answer = built(catalogue)(intro='Offline.', picks=[pick(0)])

    assert answer['delivered']['pushed'] is False
    assert 'the tablet could not be reached' in answer['delivered']['why']
    assert answer['delivered']['path'] == answer['page']['path'], 'the caller needs the path'
    assert Path(answer['page']['path']).is_file()
    assert 'on disk but not on the tablet' in caplog.text


def test_a_weather_source_that_says_it_failed_leaves_a_trace(digest, caplog):
    """The one place a weather failure left no trace anywhere — and it is the place that
    builds the page. Its sibling three lines below logs; this now does too."""
    import logging

    catalogue = digest(news={'many': 4}, weather={'answer': {'available': False, 'why': 'open-meteo answered 503'}})
    with caplog.at_level(logging.WARNING, logger='harry.capability.digest_build'):
        answer = built(catalogue)(intro='No sky.', picks=[pick(0)])

    assert 'no weather on the page' in caplog.text
    assert 'open-meteo answered 503' in caplog.text
    assert answer['page']['crowded'] == [], 'and the page is still a page'


def test_a_front_sheet_that_will_not_fit_says_so(digest):
    """`crowded` is the only thing that reports the day column falling off the front sheet.
    A flex box does not split, so it lands wholly on page two the moment it is a point too
    tall — and nothing about the answer would otherwise show it."""
    answer = built(digest(news={'many': 20}))(
        intro='An intro so long that it pushes the day column off the front sheet. ' * 24,
        picks=[pick(n) for n in range(6)],
    )

    assert any('did not fit on the front sheet' in one for one in answer['page']['crowded']), answer['page']['crowded']


@respx.mock
def test_a_second_sheet_that_runs_over_says_so(digest):
    """The other half. A reader who has turned past the front page wants everything else at a
    glance, not a second and third helping of it.

    With pictures, because a card without one is half the height and twenty of those fit
    comfortably — the sheet this is about is the one a real morning produces.
    """
    respx.get('https://pictures.test/0.jpg').mock(
        return_value=httpx.Response(200, content=A_PIXEL, headers={'content-type': 'image/png'})
    )
    answer = built(digest(news={'many': 30, 'image': 'https://pictures.test/0.jpg'}))(
        intro='Too much.',
        picks=[pick(0)],
        # Spread across the subjects: each section costs a heading, and it is the headings
        # that make six groups not fit where twenty cards in one group would have.
        more=[
            {
                'id': f'vrt-2026-09-15-story-{n}-and-what-came-of-it',
                'topic': ('belgium', 'world', 'tech', 'culture', 'sport', 'oddity')[n % 6],
            }
            for n in range(1, 21)
        ],
    )

    assert any('also today' in one for one in answer['page']['crowded']), answer['page']['crowded']


@respx.mock
def test_a_picture_is_fetched_once_per_build_and_not_once_forever(digest):
    """Harry runs for weeks on a NUC and yesterday's addresses are never asked for again, so a
    cache that outlives a build only ever grows — twenty base64 images a day, none of it
    reachable.

    Tested against `picture` and `forget` rather than through two `digest_build` calls: the
    tool renders the sheet twice on purpose, so a build's own second fetch is the thing the
    cache exists to stop, and a second *build* through the loaded tool could not be made to
    tell the two apart.
    """
    catalogue = digest(news={'many': 4})
    picture, forget = inside(catalogue, 'picture'), inside(catalogue, 'forget')

    route = respx.get('https://pictures.test/0.jpg').mock(
        return_value=httpx.Response(200, content=A_PIXEL, headers={'content-type': 'image/png'})
    )
    forget()

    first = picture('https://pictures.test/0.jpg')
    again = picture('https://pictures.test/0.jpg')
    assert first == again and route.call_count == 1, 'one build asks twice and fetches once'

    forget()
    picture('https://pictures.test/0.jpg')

    assert route.call_count == 2, 'the cache outlived the build'


def test_every_build_starts_by_forgetting_the_last_one():
    """The call that makes the test above mean something for the tool."""
    source = (REPO / '.harry' / 'tools' / 'digest_build' / 'tool.py').read_text(encoding='utf-8')
    body = source[source.index('def digest_build(') : source.index('def _deliver(')]

    assert 'forget()' in body, 'the pictures from the last build are still in memory'


def test_three_events_at_nine_share_a_column_and_the_one_at_eight_does_not(digest):
    """The reader's own correction: *"only at the hour they are overlapping should columns be
    created"*. An earlier version counted the largest overlap anywhere in the day and split
    every block by it, so three meetings colliding at 09:00 left a lone 20:00 event one third
    of a column wide."""
    catalogue = digest(
        news={'many': 4},
        icloud={
            'events': [
                {'at': '09:00', 'ends': '10:00', 'title': 'One', 'where': '', 'calendar': 'Shaun'},
                {'at': '09:15', 'ends': '09:45', 'title': 'Two', 'where': '', 'calendar': 'Kids'},
                {'at': '09:30', 'ends': '10:30', 'title': 'Three', 'where': '', 'calendar': 'Shaun'},
                {'at': '20:00', 'ends': '21:00', 'title': 'Alone', 'where': '', 'calendar': 'Kids'},
            ]
        },
    )
    answer = built(catalogue)(intro='Overlapping.', picks=[pick(0)])

    placed = inside(catalogue, 'lay_out')(
        [
            {'all_day': False, 'from': 540, 'to': 600, 'title': 'One', 'calendar': 'Shaun'},
            {'all_day': False, 'from': 555, 'to': 585, 'title': 'Two', 'calendar': 'Kids'},
            {'all_day': False, 'from': 570, 'to': 630, 'title': 'Three', 'calendar': 'Shaun'},
            {'all_day': False, 'from': 1200, 'to': 1260, 'title': 'Alone', 'calendar': 'Kids'},
        ]
    )
    widths = {event['title']: round(width, 3) for event, _, width in placed}

    assert widths == {'One': 0.333, 'Two': 0.333, 'Three': 0.333, 'Alone': 1.0}
    assert answer['page']['crowded'] == []


def test_the_reader_sets_the_name_and_the_colours(digest):
    """The two settings a person actually chooses. Neither was exercised by any test, so the
    masthead and the calendar palette were both drawn only in their default."""
    catalogue = digest(
        settings='NAME=The Bundervoet Daily\nCOLOURS=Shaun=yellow|Kids=pink',
        news={'many': 4},
        icloud={
            'events': [
                {'at': '09:00', 'ends': '10:00', 'title': 'Standup', 'where': '', 'calendar': 'Shaun'},
                {'at': 'all day', 'ends': None, 'title': 'School run', 'where': '', 'calendar': 'Kids'},
            ]
        },
    )
    answer = built(catalogue)(intro='Named.', picks=[pick(0)])

    prose = text_of(answer['page']['path'])
    assert says(prose, 'The Bundervoet Daily'), 'the masthead is still the default'
    # The legend names only the calendars with something on today, which is both of these.
    assert says(prose, 'Shaun') and says(prose, 'Kids')


STRIP = ('08:00', '12:00', '16:00', '20:00', '23:00')


def sky(**changed) -> dict:
    """A working forecast in the shape the weather connector answers, with a strip's worth of
    hours. Every other test hands over one hour."""
    return {
        'weather': {
            'answer': {
                'available': True,
                'place': 'Leuven',
                'summary': 'overcast',
                'high': 29,
                'low': 17,
                'rain_chance': 53,
                'sunrise': '07:22',
                'sunset': '19:46',
                'hours': [
                    {'at': f'{h:02d}:00', 'temperature': 15 + h, 'summary': 'clear' if h < 18 else 'rain'}
                    for h in range(6, 24)
                ],
                **changed,
            }
        }
    }


def front_runs(path: str) -> list[tuple[float, str]]:
    """Each run of text on the front sheet with where it starts, in points from the left."""
    runs: list[tuple[float, str]] = []

    def visit(text, cm, tm, font, size):
        if text.strip():
            runs.append((tm[4] * cm[0] + tm[5] * cm[2] + cm[4], text.strip()))

    PdfReader(path).pages[0].extract_text(visitor_text=visit)
    return runs


def captured(catalogue, monkeypatch) -> list[str]:
    """The HTML `digest_build` hands to `render`, kept on its way through."""
    tool = built(catalogue).__globals__
    real, seen = tool['render'], []

    def keeping(html, where, log):
        seen.append(html)
        return real(html, where, log)

    monkeypatch.setitem(tool, 'render', keeping)
    return seen


CONTENT_RIGHT = 509.34 - 34.0
"""The right edge of the text on every sheet: the Paper Pro's page less its right margin."""


def strip_cells(html: str) -> list[tuple[float, float, float]]:
    """Left and right edge of each hour's cell on the front sheet, and where its time label's
    text ends, in points, exactly as WeasyPrint lays out the page `digest_build` rendered. Read
    off the layout rather than the PDF, which says where a label starts and never where it
    ends."""
    from weasyprint import HTML

    def classes(box) -> list[str]:
        element = getattr(box, 'element', None)
        return element.get('class', '').split() if element is not None else []

    def find(box):
        if 'strip' in classes(box):
            return box
        for child in getattr(box, 'children', ()):
            if (found := find(child)) is not None:
                return found
        return None

    def text_ends(box) -> list[float]:
        """The right edge of every run of text inside a box. Only text boxes carry `text`."""
        own = [box.position_x + box.width] if isinstance(getattr(box, 'text', None), str) else []
        return own + [end for child in getattr(box, 'children', ()) for end in text_ends(child)]

    def label_end(cell) -> float:
        label = next(child for child in cell.children if 't' in classes(child))
        return max(text_ends(label))

    strip = find(HTML(string=html).render().pages[0]._page_box)
    assert strip is not None, 'no strip on the front sheet'
    return [
        (
            round(cell.border_box_x() * 72 / 96, 2),
            round((cell.border_box_x() + cell.border_width()) * 72 / 96, 2),
            round(label_end(cell) * 72 / 96, 2),
        )
        for cell in strip.children
        if 'h' in classes(cell)
    ]


def test_the_weather_strip_carries_five_hours_ending_at_eleven(digest):
    """Every other test hands over one hour, so the strip was empty everywhere and most of the
    weather icons were drawn by nothing."""
    answer = built(digest(news={'many': 4}, **sky()))(intro='Hourly.', picks=[pick(0)])

    prose = text_of(answer['page']['path'])
    assert [says(prose, at) for at in STRIP] == [True] * 5
    starts = [prose.index(at) for at in STRIP]
    assert starts == sorted(starts), 'the hours read left to right, morning to night'
    assert answer['page']['crowded'] == []


def test_the_strip_chooses_its_hours_by_the_clock_not_by_position(digest):
    """Picking every fourth entry gave 08:00 only because the list happened to start at 06:00.
    A forecast starting at 07:00 turned the same rule into 09:00, 13:00, 17:00 and 21:00."""
    late_start = [{'at': f'{h:02d}:00', 'temperature': 15 + h, 'summary': 'clear'} for h in range(7, 24)]
    answer = built(digest(news={'many': 4}, **sky(hours=late_start)))(intro='Hourly.', picks=[pick(0)])

    prose = text_of(answer['page']['path'])
    assert [says(prose, at) for at in STRIP] == [True] * 5
    assert [says(prose, at) for at in ('09:00', '13:00', '17:00', '21:00')] == [False] * 4


def test_the_eleven_oclock_hour_sits_inside_the_right_margin(digest, monkeypatch):
    """Each hour is a 25pt cell, 6pt from the next, and the strip's width is worked out from its
    hours. Set for four, it did not spill: it squeezed five into 19pt cells, which stays inside
    the page and puts the labels nearly touching. Set a cell too wide, it left a blank at the
    right end. Both are checked here, on the layout of the page that was actually rendered."""
    catalogue = digest(news={'many': 4}, **sky())
    pages = captured(catalogue, monkeypatch)
    answer = built(catalogue)(intro='Hourly.', picks=[pick(0)])

    cells = strip_cells(pages[-1])
    assert len(cells) == 5
    assert [round(right - left, 1) for left, right, _ in cells] == [25.0] * 5, 'no hour is squeezed'
    assert [round(b[0] - a[1], 1) for a, b in zip(cells, cells[1:])] == [6.0] * 4
    assert all(end <= right for _, right, end in cells), 'every time fits its own cell, so none overlaps the next'
    label, last = cells[-1][2], cells[-1][1]
    assert label <= CONTENT_RIGHT, f'the 23:00 label ends at {label}pt, past the margin at {CONTENT_RIGHT}pt'
    assert last > CONTENT_RIGHT - 31.0, f'the 23:00 cell ends at {last}pt, a whole hour short of the edge'
    assert answer['page']['crowded'] == []


def test_an_hourly_block_that_stops_before_eleven_draws_the_hours_it_has(digest, monkeypatch):
    """Nothing stands in for 23:00 — not 22:00, the last hour there is, and not an empty cell.
    The four hours keep the places they have in a full strip, so the right end is left blank."""
    early = [{'at': f'{h:02d}:00', 'temperature': 15 + h, 'summary': 'clear'} for h in range(6, 23)]
    catalogue = digest(news={'many': 4}, **sky(hours=early))
    pages = captured(catalogue, monkeypatch)
    answer = built(catalogue)(intro='Hourly.', picks=[pick(0)])

    prose = text_of(answer['page']['path'])
    assert [says(prose, at) for at in STRIP[:4]] == [True] * 4
    assert not says(prose, '23:00') and not says(prose, '22:00')

    # Built second: both write today's file to the same place.
    full = digest(news={'many': 4}, **sky())
    full_pages = captured(full, monkeypatch)
    built(full)(intro='Hourly.', picks=[pick(0)])
    # Four cells, not five: an empty one for 23:00 would be a fifth. The full strip is counted
    # first, so two empty lists cannot agree.
    full_cells = strip_cells(full_pages[-1])
    assert len(full_cells) == 5
    assert strip_cells(pages[-1]) == full_cells[:4], 'each hour keeps its place'


def test_no_forecast_draws_dashes_with_no_place_and_no_sun(digest):
    """What the panel does today when the forecast failed: `digest_build` hands it an empty
    answer. The place went with the hard-coded Leuven, because nothing supplies one here."""
    down = {'weather': {'answer': {'available': False, 'place': 'Leuven', 'why': 'open-meteo could not be reached'}}}
    answer = built(digest(news={'many': 4}, **down))(intro='No sky.', picks=[pick(0)])

    prose = text_of(answer['page']['path'])
    assert says(prose, 'High –° · Low –°') and says(prose, 'Rain –%')
    assert not says(prose, 'Leuven') and not says(prose, 'Sunrise')
    assert [text for _, text in front_runs(answer['page']['path']) if text in STRIP] == []
    assert says(prose, 'No sky.'), 'the rest of the page renders'
    assert answer['page']['crowded'] == []


def test_each_hour_on_the_strip_draws_its_own_sky(digest, monkeypatch):
    """Five hours, five different skies, and a day whose own icon is none of them — so a strip
    that drew the day's icon, or one icon for every hour, cannot pass."""
    skies = dict(zip(STRIP, ('clear', 'fog', 'rain', 'thunderstorm', 'snow'), strict=True))
    hours = [{'at': at, 'temperature': 20, 'summary': summary} for at, summary in skies.items()]
    catalogue = digest(news={'many': 4}, **sky(summary='overcast', hours=hours))
    pages = captured(catalogue, monkeypatch)
    built(catalogue)(intro='Every sky.', picks=[pick(0)])
    face = inside(catalogue, 'face')

    drawn = {at: face(summary, size=15) for at, summary in skies.items()}
    assert len(set(drawn.values()) | {face('overcast', size=15)}) == 6, 'the six skies must look different'
    strip = pages[-1].split('<div class="strip">', 1)[1]
    cells = strip.split('<div class="h">')[1:]
    assert len(cells) == 5
    for at, cell in zip(STRIP, cells, strict=True):
        assert f'<div class="t">{at}</div>' in cell
        assert drawn[at] in cell, f'{at} does not draw {skies[at]}'


def test_the_panel_says_when_the_sun_rises_and_sets(digest):
    answer = built(digest(news={'many': 4}, **sky()))(intro='Sunny.', picks=[pick(0)])

    assert says(text_of(answer['page']['path']), 'Sunrise 07:22 · Sunset 19:46')


def test_a_forecast_with_no_sun_prints_no_sun_line_and_keeps_the_rest(digest):
    """The weather connector answers None for a time it could not read."""
    answer = built(digest(news={'many': 4}, **sky(sunrise=None, sunset=None)))(intro='Grey.', picks=[pick(0)])

    prose = text_of(answer['page']['path'])
    assert not says(prose, 'Sunrise') and not says(prose, 'Sunset')
    assert says(prose, 'High 29°') and says(prose, 'Rain 53%')
    assert [says(prose, at) for at in STRIP] == [True] * 5


def test_one_time_of_the_two_still_prints(digest):
    answer = built(digest(news={'many': 4}, **sky(sunrise=None)))(intro='Grey.', picks=[pick(0)])

    prose = text_of(answer['page']['path'])
    assert says(prose, 'Sunset 19:46')
    assert not says(prose, 'Sunrise')


@respx.mock
def test_the_real_forecast_reaches_the_panel(digest, tmp_path, monkeypatch):
    """Every other test here hands the page a stand-in. This one runs the real weather
    connector against the answer recorded in Leuven on 19 September 2026, so a key the
    connector names one way and the page reads another cannot pass.

    Set to Ghent, because the panel used to print Leuven whatever the setting said."""
    for key in ('LATITUDE', 'LONGITUDE', 'TIMEZONE', 'PLACE'):
        monkeypatch.delenv(f'HARRY_WEATHER_{key}', raising=False)
    real = copy_capability(REPO / '.harry' / 'connectors' / 'weather', tmp_path / 'root' / 'connectors' / 'weather')
    (real / '.env.local').write_text('PLACE=Ghent\n', encoding='utf-8')
    recording = json.loads((REPO / 'tests' / 'fixtures' / 'weather' / 'leuven-sun.json').read_text(encoding='utf-8'))
    respx.get('https://api.open-meteo.com/v1/forecast').mock(return_value=httpx.Response(200, json=recording))

    answer = built(digest(sources=('news',), news={'many': 4}))(intro='Real sky.', picks=[pick(0)])

    prose = text_of(answer['page']['path'])
    assert says(prose, 'Sunrise 07:22 · Sunset 19:46')
    assert says(prose, 'Rain 53% · Ghent')
    assert not says(prose, 'Leuven')
    # 16.1, 19.3, 22.6, 21.2 and 20.0 in the recording, rounded.
    temperatures = [text for _, text in front_runs(answer['page']['path']) if text.endswith('°')]
    assert temperatures[-5:] == ['16°', '19°', '23°', '21°', '20°']


def test_the_file_a_reader_opens_is_the_size_and_shape_it_should_be(digest):
    """Read back off the PDF, not off what `render` computed from its own document object.
    The tablet opens the file."""
    answer = built(digest(news={'many': 6}))(
        intro='Read back.',
        picks=[pick(0), pick(1)],
        more=[{'id': 'vrt-2026-09-15-story-2-and-what-came-of-it', 'topic': 'tech'}],
    )
    reader = PdfReader(answer['page']['path'])

    box = reader.pages[0].mediabox
    assert (round(float(box.width), 2), round(float(box.height), 2)) == (509.34, 679.13)

    def titles(outline) -> list[str]:
        """The outline is a tree — a list holding entries and nested lists of entries."""
        out = []
        for one in outline:
            out += titles(one) if isinstance(one, list) else [str(one.get('/Title'))]
        return out

    named = titles(reader.outline)
    assert named[0] == 'The day', 'the front page is where the navigator starts'
    assert sum(name.startswith('Story ') for name in named) == 3, named

    annotations = sum(len(page.get('/Annots') or []) for page in reader.pages)
    assert annotations > 20, f'{annotations} tappable things — the tablet has no address bar'


def test_an_id_that_is_a_beginning_of_two_candidates_is_refused(digest):
    """The safety property the whole resolution rule rests on, and it is not "ids never begin
    one another" — they can.

    The news connector disambiguates two same-day stories whose first five title words match
    by appending `-2`, so `…-de-huur` and `…-de-huur-2` are both real ids and the first is a
    strict prefix of the second. A truncation that lands on the shorter one must therefore be
    refused rather than resolved to either, and that refusal is what sends Claude back to look
    the id up again.
    """
    catalogue = digest(news={'many': 4, 'collide': True})
    base = 'vrt-2026-09-15-story-0-and-what-came-of-it'

    with pytest.raises(Exception, match='could mean any of'):
        built(catalogue)(intro='Colliding.', picks=[pick(0, id=base[:-6])])


def test_an_exact_match_always_wins_over_a_longer_candidate(digest):
    """The other half. With `X` and `X-2` both real, asking for `X` means `X` — anything else
    would silently hand back a story nobody chose, and `resolved` would stay empty."""
    catalogue = digest(news={'many': 4, 'collide': True})
    base = 'vrt-2026-09-15-story-0-and-what-came-of-it'

    answer = built(catalogue)(intro='Exact.', picks=[pick(0, id=base)])

    assert answer['resolved'] == [], 'nothing needed resolving'
    assert says(text_of(answer['page']['path']), 'Story 0')


def test_the_page_goes_to_the_folder_the_digest_names(digest):
    """Where a document belongs is something only the thing producing it knows. A weekly
    digest would want its own folder, and the tablet connector has no way to tell them apart."""
    catalogue = digest(
        sources=('weather', 'icloud', 'news', 'remarkable'),
        settings='FOLDER=🗞️ Daily',
        news={'many': 4},
    )
    answer = built(catalogue)(intro='Filed.', picks=[pick(0)])

    tablet = catalogue.get('connector', 'remarkable')
    assert tablet is not None and tablet.target is not None
    assert [name for _, name, folder in tablet.target.pushed] == [today()]
    assert [folder for _, _, folder in tablet.target.pushed] == ['🗞️ Daily']
    assert answer['delivered']['where'] == '🗞️ Daily'


def test_an_empty_folder_setting_leaves_it_to_the_tablet(digest):
    """The default, and the reason it is empty rather than a name: one place decides where
    ad-hoc documents go, and it is the connector."""
    catalogue = digest(sources=('weather', 'icloud', 'news', 'remarkable'), news={'many': 4})
    built(catalogue)(intro='Wherever.', picks=[pick(0)])

    tablet = catalogue.get('connector', 'remarkable')
    assert tablet is not None and tablet.target is not None
    assert [folder for _, _, folder in tablet.target.pushed] == [None], 'the connector was not left to decide'


def test_the_docs_say_the_folder_belongs_to_whoever_is_pushing():
    """The line this drew, and the one a reader needs when a folder appears that they did not
    make."""
    page = ' '.join((REPO / 'docs' / 'morning-page.md').read_text(encoding='utf-8').split())
    sources = ' '.join((REPO / 'docs' / 'sources.md').read_text(encoding='utf-8').split())
    runbook = ' '.join(
        (REPO / '.harry' / 'connectors' / 'remarkable' / 'CONNECTOR.md').read_text(encoding='utf-8').split()
    )

    assert 'FOLDER=🗞️ Daily' in page
    for prose in (sources, runbook):
        assert 'Whoever is pushing says which folder' in prose
        assert 'top level' in prose, 'a caller must not be able to write inside your folders'
