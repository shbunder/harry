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
import re
import sys
import xml.etree.ElementTree as ET
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


INTRO = (
    'A grey Saturday: breakfast in Aarschot at nine, gymnastics at eleven, then the afternoon '
    'is yours. Drizzle until noon and around 21 degrees after, so the walk is better left for '
    'four. The front page leads on the forty-four municipalities asking for more time with the '
    'housing duty — three papers, three angles — and on a quiet night abroad, with the Dutch '
    'railways back to a normal timetable after Thursday. Further in: a robot that sorts parcels '
    'in Willebroek, a new exhibition at M Leuven, and a council vote in Holsbeek on the '
    'Kortrijksebaan crossing that the school has been asking about since spring.'
)
"""An intro the length a real one runs to. It decides how much room the timetable gets, and
the one-line intros most tests use leave about ninety points more than a morning does."""


def drawn(catalogue, monkeypatch) -> dict:
    """The page's HTML, caught on its way to the renderer.

    Through the tool, not beside it: everything that decides the page — the measuring, the
    fitting, the composing — has run by the time `render` is called, and the test reads what
    production would have printed. The PDF is still written.
    """
    tool = built(catalogue).__globals__
    real, caught = tool['render'], {}

    def spy(html, where, log):
        caught['html'] = html
        return real(html, where, log)

    monkeypatch.setitem(tool, 'render', spy)
    return caught


def the_sheet(html: str) -> str:
    """The second sheet's part of the page: from its own `div` to the first article."""
    start = html.index('<div class="sheet two" id="more">')
    return html[start : html.index('<article', start)]


def the_hours(html: str) -> tuple[list[int], float]:
    """The hours the timetable labels, and how tall its grid is drawn, in points."""
    hours = [int(h) for h in re.findall(r'<div class="hour" style="top:[\d.]+pt"><span>(\d\d)</span>', html)]
    grid = re.search(r'<div class="grid" style="height:([\d.]+)pt">', html)
    assert grid, 'no timetable on the page'
    return hours, float(grid.group(1))


def links(path: str) -> list[list[tuple[str, float, float]]]:
    """Every internal link on every page of the PDF, as `(destination, left, top)` in points.

    Read off the file the tablet opens. A link WeasyPrint did not write — it writes none for an
    `<a>` that is itself a flex item — is simply not here, which is the point.
    """
    reader = PdfReader(path)
    out = []
    for page in reader.pages:
        found = []
        for annotation in page.get('/Annots') or []:
            one = annotation.get_object()
            if one.get('/Subtype') == '/Link' and '/Dest' in one:
                x0, y0, _, y1 = (float(v) for v in one['/Rect'])
                found.append((str(one['/Dest']), round(x0, 1), round(max(y0, y1), 1)))
        out.append(found)
    return out


def starts(path: str) -> dict[str, int]:
    """Which page each named place begins on — `more`, `story3`, and so on."""
    reader = PdfReader(path)
    found = {name: reader.get_destination_page_number(dest) for name, dest in reader.named_destinations.items()}
    return {name: page for name, page in found.items() if page is not None}


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
    """Home, abroad, technology, culture, sport, what is nearby, and the one worth knowing. The
    topic is not decoration, it is the running order — so a caller may hand them over in any
    order. The day's news is at the front; the reader's own interests are at the back."""
    answer = built(digest(news={'many': 6}))(
        intro='Ordered.',
        picks=[
            {'id': 'vrt-2026-09-15-story-0-and-what-came-of-it', 'note': 'An oddity.', 'topic': 'oddity'},
            {'id': 'vrt-2026-09-15-story-1-and-what-came-of-it', 'note': 'Abroad.', 'topic': 'world'},
            {'id': 'vrt-2026-09-15-story-2-and-what-came-of-it', 'note': 'At home.', 'topic': 'belgium'},
            {
                'id': 'vrt-2026-09-15-story-3-and-what-came-of-it',
                'note': 'Round the corner.',
                'topic': 'regional',
                'also': ['vrt-2026-09-15-story-4-and-what-came-of-it'],
            },
        ],
    )

    prose = text_of(answer['page']['path'])
    assert prose.index('At home.') < prose.index('Abroad.')
    assert prose.index('Abroad.') < prose.index('Round the corner.') < prose.index('An oddity.')


def test_a_nearby_pick_is_marked_as_its_own_topic_not_left_unknown(digest):
    """An unknown topic sorts near the end *and* draws no mark, so `regional` shares its shape
    of failure twice over. Sorting is checked below; the mark is checked on the module the
    tool actually loaded, because the drawing never reaches the extracted text."""
    answer = built(digest(news={'many': 4}))(
        intro='Marked.',
        picks=[
            {'id': 'vrt-2026-09-15-story-0-and-what-came-of-it', 'note': 'At home.', 'topic': 'belgium'},
            {
                'id': 'vrt-2026-09-15-story-1-and-what-came-of-it',
                'note': 'Round the corner.',
                'topic': 'regional',
                'also': ['vrt-2026-09-15-story-2-and-what-came-of-it'],
            },
            {'id': 'vrt-2026-09-15-story-3-and-what-came-of-it', 'note': 'A guess.', 'topic': 'nonsense'},
        ],
    )

    assert Path(answer['page']['path']).exists()
    prose = text_of(answer['page']['path'])
    # A topic the table does not carry sorts after every one it does. `regional` sorting
    # before it is what says the table carries it, rather than it having been ignored.
    assert prose.index('At home.') < prose.index('Round the corner.') < prose.index('A guess.')

    # And it is drawn. Sorting alone passed with `regional` deleted from the table, because an
    # unknown topic keeps the order it was handed in.
    marks = next(sys.modules[name] for name in list(sys.modules) if name.endswith('.marks'))
    drawn = marks.badge('regional')
    assert '<svg' in drawn and '<path' in drawn, f'nearby has no mark of its own: {drawn!r}'
    assert marks.badge('nonsense') == '', 'a topic the table does not carry was given a mark'


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


def test_the_weather_strip_carries_four_hours(digest):
    """Every other test hands over one hour, so the strip was empty everywhere and fifteen of
    the sixteen weather icons were drawn by nothing."""
    hours = [
        {'at': f'{h:02d}:00', 'temperature': 15 + h, 'summary': 'clear' if h < 18 else 'rain'} for h in range(6, 23)
    ]
    catalogue = digest(
        news={'many': 4},
        weather={
            'answer': {
                'available': True,
                'place': 'Leuven',
                'summary': 'overcast',
                'high': 29,
                'low': 17,
                'rain_chance': 53,
                'hours': hours,
            }
        },
    )
    answer = built(catalogue)(intro='Hourly.', picks=[pick(0)])

    prose = text_of(answer['page']['path'])
    assert [says(prose, at) for at in ('08:00', '12:00', '16:00', '20:00')] == [True] * 4
    assert answer['page']['crowded'] == []


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


def test_a_nearby_story_cannot_lead_on_one_local_paper_alone(digest):
    """The three towns are a standing interest, not the day's news, so a local item earns the
    front page by being somebody else's story too. `also` is where Claude says that, and the
    check is on `also` existing rather than on which paper it names — deciding whether a
    source counts as national would be Harry reading the news."""
    made = built(digest(news={'many': 4}))

    with pytest.raises(Exception) as refused:
        made(
            intro='One paper only.',
            picks=[{'id': 'vrt-2026-09-15-story-0-and-what-came-of-it', 'note': 'Alone.', 'topic': 'regional'}],
        )
    assert 'another paper carries it' in str(refused.value)
    assert 'vrt-2026-09-15-story-0-and-what-came-of-it' in str(refused.value), 'it does not say which pick'


def test_a_nearby_story_may_lead_when_another_paper_carries_it(digest):
    """The same pick, with a companion, goes through. Without this the rule above would pass
    just as well if the tool refused every regional pick outright."""
    answer = built(digest(news={'many': 4}))(
        intro='Two papers.',
        picks=[
            {
                'id': 'vrt-2026-09-15-story-0-and-what-came-of-it',
                'note': 'Carried elsewhere too.',
                'topic': 'regional',
                'also': ['vrt-2026-09-15-story-1-and-what-came-of-it'],
            }
        ],
    )

    assert answer['front'] == 1
    assert 'Carried elsewhere too.' in text_of(answer['page']['path'])


def test_a_nearby_story_on_the_second_sheet_needs_no_companion(digest):
    """`more` is a glance, not an argument — the rule is about leading the paper, so a nearby
    story with nobody else behind it belongs there rather than nowhere.

    Checked by the story's own link on the sheet. This read the word "Nearby" off the page
    while the sheet had a heading by that name; it has none now."""
    answer = built(digest(news={'many': 6}))(
        intro='A glance.',
        picks=[pick(0)],
        more=[{'id': 'vrt-2026-09-15-story-1-and-what-came-of-it', 'topic': 'regional'}],
    )

    assert answer['more'] == 1
    sheet = starts(answer['page']['path'])['more']
    assert 'story2' in [dest for dest, _, _ in links(answer['page']['path'])[sheet]]


def test_every_place_that_lists_the_topics_agrees():
    """The topics are written out in four places and only one of them executes.

    `marks.py` is the running order. `digest_build/TOOL.md` is what Claude reads when it calls
    this tool. The brief is what it reads before choosing. The fourth is a copy of the brief in
    the claude.ai routine, which no test can reach.

    This caught a real one: the brief said "exactly one of these six words" above a table of
    seven, and a model following the count rather than the table never emits the seventh at
    all — which is silent, because a topic nobody uses looks exactly like a quiet week.
    """
    import re

    marks = (REPO / '.harry' / 'tools' / 'digest_build' / 'marks.py').read_text(encoding='utf-8')
    topics = re.findall(r"^    '(\w+)': \(", marks, re.MULTILINE)
    assert len(topics) >= 6, topics

    body = (REPO / '.harry' / 'tools' / 'digest_build' / 'TOOL.md').read_text(encoding='utf-8')
    listed = re.search(r'`topic` is one of ([^,]+(?:, [^,]+)*), and it', body)
    assert listed, 'the tool body no longer says what a topic may be'
    assert re.findall(r'`(\w+)`', listed.group(1)) == topics, 'the tool body and the running order disagree'

    brief = (REPO / '.harry' / 'jobs' / 'morning-page' / 'JOB.md').read_text(encoding='utf-8')
    rows = re.findall(r'^\| `(\w+)` \|', brief, re.MULTILINE)
    assert sorted(rows) == sorted(topics), f'the brief lists {rows}, the paper runs {topics}'

    counts = re.findall(r'(?:one of these|from the) (\w+) words', brief)
    assert counts, 'the brief no longer says how many topic words there are'
    written = {'six': 6, 'seven': 7, 'eight': 8, 'nine': 9}
    for said in counts:
        assert written.get(said) == len(topics), f'the brief says {said} topic words and there are {len(topics)}'


@respx.mock
def test_a_card_is_illustrated_from_the_article_when_the_feed_had_no_picture(digest):
    """Three of five feeds publish no picture at all, so without this their cards are the plain
    ones on an otherwise illustrated page. `article()` answers with the feed's picture or the
    page's; this is the half that puts the second one on the sheet."""
    drawn = respx.get('https://pictures.test/page.jpg').mock(
        return_value=httpx.Response(200, content=A_PIXEL, headers={'content-type': 'image/png'})
    )
    answer = built(digest(news={'many': 4, 'page_image': 'https://pictures.test/page.jpg'}))(
        intro='From the page.', picks=[pick(0)]
    )

    assert drawn.called, 'the article picture was never fetched'
    assert answer['page']['crowded'] == []
    assert 'Why story 0 matters.' in text_of(answer['page']['path'])


# ---- the front page's way onward -------------------------------------------------------------


def test_the_way_to_the_second_sheet_is_in_the_column_head_above_the_stories(digest):
    """It was a button pinned under the six stories by a spacer. The timetable's hours are
    absolutely positioned, so the left column had no height of its own, the right column was
    stretched shorter than its stories, and the button landed across the fifth.

    Read off the PDF: the one link on the front page that goes to the second sheet sits above
    every link that goes to a story. A button under the list, or on top of it, is below one."""
    answer = built(digest(news={'many': 12}))(
        intro=INTRO,
        picks=[pick(n) for n in range(6)],
        more=[{'id': f'vrt-2026-09-15-story-{n}-and-what-came-of-it', 'topic': 'world'} for n in range(6, 9)],
    )

    front = links(answer['page']['path'])[0]
    onward = [top for dest, _, top in front if dest == 'more']
    stories = [top for dest, _, top in front if dest.startswith('story')]
    assert len(onward) == 1, f'{len(onward)} links to the second sheet on the front page'
    assert stories and onward[0] > max(stories), 'the way onward is not above the stories'

    first = PdfReader(answer['page']['path']).pages[0].extract_text() or ''
    assert says(first, 'Other news'), 'the column head does not say where it goes'
    assert not says(first, 'by subject'), 'the old button is still drawn'


def test_with_no_second_sheet_nothing_offers_a_way_to_it(digest):
    """No `more`, no sheet — and no link to one. The article pages linked to `#more` whether
    or not it existed, so on such a day that link went nowhere."""
    answer = built(digest(news={'many': 4}))(intro='Front only.', picks=[pick(0), pick(1)])

    prose = text_of(answer['page']['path'])
    assert not says(prose, 'Other news'), 'a way to a sheet that is not there'
    assert says(prose, 'The front page'), 'the article pages lost their other way out'
    assert all(dest != 'more' for page in links(answer['page']['path']) for dest, _, _ in page)


def test_an_article_page_calls_the_second_sheet_other_news(digest):
    """One place, one name: the front page's column head and every article page's foot."""
    answer = built(digest(news={'many': 4}))(
        intro='Named.',
        picks=[pick(0)],
        more=[{'id': 'vrt-2026-09-15-story-1-and-what-came-of-it', 'topic': 'tech'}],
    )

    at = starts(answer['page']['path'])
    reader = PdfReader(answer['page']['path'])
    article = ' '.join((reader.pages[at['story1']].extract_text() or '').split())
    assert says(article, 'Other news')
    assert not says(article, 'Other articles')
    assert 'more' in [dest for dest, _, _ in links(answer['page']['path'])[at['story1']]]


# ---- the timetable fills its column ----------------------------------------------------------


def event(at: str, ends: str, title: str = 'Something') -> dict:
    return {'at': at, 'ends': ends, 'title': title, 'where': '', 'calendar': 'Shaun'}


def test_a_quiet_days_timetable_shows_more_of_the_day_and_reaches_the_foot(digest, monkeypatch):
    """Six hours at 34pt came to 204pt of a 302pt column on 2026-09-19, and the bottom third of
    the front page was white. A quiet day now shows later hours rather than stopping short."""
    catalogue = digest(news={'many': 4}, icloud={'events': [event('09:30', '11:30')]})
    caught = drawn(catalogue, monkeypatch)
    answer = built(catalogue)(intro=INTRO, picks=[pick(0)])

    hours, grid = the_hours(caught['html'])
    room = answer['fits']['timetable']
    assert room > 6 * 34, f'the column has {room}pt, which six hours already fill'
    assert max(hours) > 13, f'the timetable stops at {max(hours)}:00'
    assert abs(grid - room) < 0.5, f'the grid is {grid}pt of the {room}pt it was given'
    assert grid / len(hours) <= 34.0, 'an hour is drawn taller than 34pt'
    assert answer['page']['crowded'] == []


def test_a_busy_days_timetable_is_not_stretched_or_extended(digest, monkeypatch):
    """07:00 to 21:00 already needs sixteen rows. It shows those, at 18pt or more, and no more
    of the evening than the last event reaches into."""
    catalogue = digest(news={'many': 4}, icloud={'events': [event('07:00', '08:00'), event('20:00', '21:00')]})
    caught = drawn(catalogue, monkeypatch)
    built(catalogue)(intro=INTRO, picks=[pick(0)])

    hours, grid = the_hours(caught['html'])
    assert hours == list(range(7, 23)), hours
    assert grid / len(hours) >= 18.0, f'{grid / len(hours):.1f}pt an hour is too small to read'


def test_a_day_with_nothing_timed_still_fits_its_column(digest, monkeypatch):
    """A free day, or a calendar that could not be read. It drew fifteen hours at a fixed 24pt,
    360pt against about 300 of room, and the whole day column went to page two."""
    catalogue = digest(news={'many': 4}, icloud={'events': []})
    caught = drawn(catalogue, monkeypatch)
    answer = built(catalogue)(intro=INTRO, picks=[pick(0)])

    hours, grid = the_hours(caught['html'])
    assert hours == list(range(7, 22)), hours
    assert abs(grid - answer['fits']['timetable']) < 0.5, f'the grid is {grid}pt of {answer["fits"]["timetable"]}'
    assert answer['page']['crowded'] == [], answer['page']['crowded']


def test_a_day_too_long_for_its_column_is_reported_rather_than_squeezed(digest, monkeypatch):
    """Eighteen hours at 18pt is 324pt. Below 18pt a half-hour meeting cannot show its own name,
    so the hours stay readable and the day column moves — and `crowded` says so, because it is
    the only thing that would."""
    catalogue = digest(news={'many': 4}, icloud={'events': [event('06:00', '07:00'), event('22:00', '23:00')]})
    caught = drawn(catalogue, monkeypatch)
    answer = built(catalogue)(intro=INTRO, picks=[pick(0)])

    hours, grid = the_hours(caught['html'])
    assert answer['fits']['timetable'] < len(hours) * 18.0, 'this day fits; the test needs one that does not'
    assert grid / len(hours) == pytest.approx(18.0)
    assert any('did not fit on the front sheet' in one for one in answer['page']['crowded']), answer['page']['crowded']


# ---- the second sheet ------------------------------------------------------------------------

EIGHTEEN = ['oddity', 'world', 'belgium', 'culture', 'tech', 'world', 'belgium', 'belgium', 'regional']
EIGHTEEN = EIGHTEEN + EIGHTEEN[::-1]


def test_the_second_sheet_is_three_columns_of_marked_stories_in_the_papers_order(digest, monkeypatch):
    """No section headings. Each story carries its topic's mark, and the paper's order —
    home, abroad, technology, culture, sport, nearby, the one worth knowing — is kept whatever
    order they were handed in.

    Three columns is read off the PDF, from where the stories' links landed. A `column-count`
    in the stylesheet that the sheet's markup does not use would pass a check on the CSS."""
    catalogue = digest(news={'many': 24})
    caught = drawn(catalogue, monkeypatch)
    more = [{'id': f'vrt-2026-09-15-story-{n}-and-what-came-of-it', 'topic': t} for n, t in enumerate(EIGHTEEN, 1)]
    answer = built(catalogue)(intro='Eighteen.', picks=[pick(0)], more=more)

    sheet = the_sheet(caught['html'])
    assert '<h2' not in sheet, 'a section heading is still drawn'
    assert sheet.count('<svg class="topic"') == len(more), 'a story on the sheet has no mark'

    handed = {f'story{place}': one['topic'] for place, one in enumerate(more, start=2)}
    running = [handed[a] for a in re.findall(r'<a class="lead" href="#(story\d+)"', sheet)]
    order = ['belgium', 'world', 'tech', 'culture', 'sport', 'regional', 'oddity']
    assert running == sorted(running, key=order.index), running
    assert len(running) == len(more)

    # A link is written once per piece of text it holds — the headline, the source beside its
    # mark — so a story's column is where the leftmost of its pieces starts.
    page = starts(answer['page']['path'])['more']
    leftmost: dict[str, float] = {}
    for dest, left, _ in links(answer['page']['path'])[page]:
        if re.fullmatch(r'story\d+', dest):
            leftmost[dest] = min(left, leftmost.get(dest, left))
    lefts = set(leftmost.values())
    assert len(lefts) == 3, f'the stories stand in {len(lefts)} columns: {sorted(lefts)}'


@respx.mock
def test_the_story_opening_each_run_leads_it(digest, monkeypatch):
    """Every k-th story — k is what the sheet was fitted at — carries its picture, a larger
    headline and the first sentence of its summary. The rest are headline and source. Every
    headline is whole, and a companion still gets its line."""
    respx.get('https://pictures.test/0.jpg').mock(
        return_value=httpx.Response(200, content=A_PIXEL, headers={'content-type': 'image/png'})
    )
    catalogue = digest(
        news={
            'many': 14,
            'image': 'https://pictures.test/0.jpg',
            'real_titles': True,
            'summary': 'The first sentence says what happened. The second would not fit.',
        }
    )
    caught = drawn(catalogue, monkeypatch)
    more: list[dict] = [
        {'id': f'vrt-2026-09-15-story-{n}-and-what-came-of-it', 'topic': 'belgium'} for n in range(1, 11)
    ]
    more[4]['also'] = ['vrt-2026-09-15-story-12-and-what-came-of-it']
    answer = built(catalogue)(intro='Runs.', picks=[pick(0)], more=more)

    every = answer['fits']['sheet']['every']
    stories = the_sheet(caught['html']).split('<div class="story')[1:]
    assert len(stories) == 10
    for place, one in enumerate(stories):
        opens = place % every == 0
        assert one.startswith(' opens"') == opens, (place, every)
        assert ('<img' in one) == opens, f'story {place}: a picture where there should {"" if opens else "not "}be one'
        assert ('The first sentence says what happened.' in one) == opens
        assert 'The second would not fit' not in one
        assert 'verkennend onderzoek' in one and '…' not in one.split('class="head">')[1].split('<')[0]

    assert '<a class="one" href="#story6-1">' in stories[4], 'the companion lost its line'


@respx.mock
def test_the_second_sheet_takes_the_fewest_pages_then_the_fullest_last_page(digest, monkeypatch):
    """The ladder is tried in full for each day, and the choice is checked against every
    setting rendered independently here. Fewest pages first — a day that fits one page gets
    one — and among those the setting that leaves the least white under its columns.

    Twenty, with pictures and full-length headlines, is the heaviest sheet the tool accepts;
    ten is a light day."""
    respx.get('https://pictures.test/0.jpg').mock(
        return_value=httpx.Response(200, content=A_PIXEL, headers={'content-type': 'image/png'})
    )
    from weasyprint import HTML

    for many in (20, 10):
        catalogue = digest(news={'many': 30, 'image': 'https://pictures.test/0.jpg', 'real_titles': True})
        tool = built(catalogue).__globals__
        real_fit, kept = tool['fit'], {}
        page = real_fit.__globals__

        def keep(intro, data, log, real_fit=real_fit, kept=kept):
            kept['data'] = data
            return real_fit(intro, data, log)

        monkeypatch.setitem(tool, 'fit', keep)
        more = [
            {'id': f'vrt-2026-09-15-story-{n}-and-what-came-of-it', 'topic': EIGHTEEN[n % len(EIGHTEEN)]}
            for n in range(1, many + 1)
        ]
        answer = built(catalogue)(intro='Fitted.', picks=[pick(0)], more=more)

        second_page, style, boxes = page['second_page'], page['STYLE'], page['_boxes']
        rest = page['in_reading_order']([a for a in kept['data']['articles'] if not a['front']])
        tried = []
        for every, tall in page['LADDER']:
            done = HTML(string=f'<style>{style}</style>{second_page(rest, every, tall)}').render()
            lowest = max(low for _, _, low in boxes(done.pages[-1]))
            tried.append((len(done.pages), lowest, every, tall))
        fewest = min(pages for pages, _, _, _ in tried)
        fullest = max(low for pages, low, _, _ in tried if pages == fewest)

        chosen = answer['fits']['sheet']
        mine = next(t for t in tried if (t[2], t[3]) == (chosen['every'], chosen['picture']))
        assert mine[0] == fewest, f'{many} stories: {mine[0]} pages where {fewest} would do — {tried}'
        assert mine[1] == pytest.approx(fullest), f'{many} stories: not the fullest last page — {tried}'
        assert chosen['pages'] <= 2, chosen
        assert [one for one in answer['page']['crowded'] if 'also today' in one] == []

        at = starts(answer['page']['path'])
        first_article = min(page for name, page in at.items() if name.startswith('story'))
        assert first_article - at['more'] == chosen['pages'], 'the sheet printed is not the sheet chosen'


@respx.mock
def test_a_sheet_that_cannot_fit_two_pages_still_renders_and_says_so(digest, monkeypatch):
    """Twenty real stories fit one page at the ladder's leaner end, so nothing a caller can send
    reaches this. The ladder is cut to one generous setting to make it happen: the page still
    renders, and `crowded` — the only report of it — fires."""
    respx.get('https://pictures.test/0.jpg').mock(
        return_value=httpx.Response(200, content=A_PIXEL, headers={'content-type': 'image/png'})
    )
    catalogue = digest(news={'many': 30, 'image': 'https://pictures.test/0.jpg', 'real_titles': True})
    page = built(catalogue).__globals__['fit'].__globals__
    monkeypatch.setitem(page, 'LADDER', ((1, 240.0),))

    answer = built(catalogue)(
        intro='Too much.',
        picks=[pick(0)],
        more=[{'id': f'vrt-2026-09-15-story-{n}-and-what-came-of-it', 'topic': 'world'} for n in range(1, 21)],
    )

    assert answer['fits']['sheet']['pages'] >= 3, answer['fits']['sheet']
    assert any('also today' in one and 'runs to' in one for one in answer['page']['crowded']), answer['page']['crowded']
    assert Path(answer['page']['path']).is_file()


def recorded_summary(feed: str, title: str) -> str:
    """One item's summary exactly as the feed sent it, out of its recorded fixture."""
    items = ET.parse(REPO / 'tests' / 'fixtures' / 'news' / feed).iter('item')
    return next(i for i in items if i.findtext('title') == title).findtext('description') or ''


def test_a_summary_that_arrives_as_html_prints_as_its_first_sentence(digest):
    """KW sends its summary as HTML — a paragraph, a link, and character codes. Escaped as it
    came, the page printed the angle brackets."""
    summary = recorded_summary('kw-west-vlaanderen.xml', 'Ardooise senioren nemen sportieve start')
    assert '<p>' in summary, 'the fixture no longer carries what this is about'

    answer = built(digest(news={'many': 4, 'summary': summary}))(
        intro='Markup.',
        picks=[pick(0)],
        more=[{'id': 'vrt-2026-09-15-story-1-and-what-came-of-it', 'topic': 'regional'}],
    )

    prose = text_of(answer['page']['path'])
    assert 'Na een welverdiende pauze zijn de senioren opnieuw gestart met hun wekelijkse sportuurtje.' in prose
    assert '<' not in prose, 'markup reached the page'


@respx.mock
def test_a_fuller_second_page_does_not_beat_a_single_page(digest, monkeypatch):
    """Fewest pages first. On the real ladder a two-page setting has never filled its last page
    better than the best one-page setting did, so the two rules have agreed on every day
    measured — this forces the case where they would not. Ten stories at one tall picture each
    fill most of a second page; at the lean setting they fit one page with room over. One page
    wins."""
    respx.get('https://pictures.test/0.jpg').mock(
        return_value=httpx.Response(200, content=A_PIXEL, headers={'content-type': 'image/png'})
    )
    catalogue = digest(news={'many': 14, 'image': 'https://pictures.test/0.jpg', 'real_titles': True})
    tool = built(catalogue).__globals__
    real_fit, kept = tool['fit'], {}
    page = real_fit.__globals__
    monkeypatch.setitem(page, 'LADDER', ((1, 170.0), (8, 44.0)))

    def keep(intro, data, log):
        kept['data'] = data
        return real_fit(intro, data, log)

    monkeypatch.setitem(tool, 'fit', keep)
    answer = built(catalogue)(
        intro='One page.',
        picks=[pick(0)],
        more=[{'id': f'vrt-2026-09-15-story-{n}-and-what-came-of-it', 'topic': 'world'} for n in range(1, 11)],
    )

    from weasyprint import HTML

    rest = page['in_reading_order']([a for a in kept['data']['articles'] if not a['front']])
    measured = {}
    for every, tall in page['LADDER']:
        done = HTML(string=f'<style>{page["STYLE"]}</style>{page["second_page"](rest, every, tall)}').render()
        measured[every] = (len(done.pages), max(low for _, _, low in page['_boxes'](done.pages[-1])))
    assert measured[1][0] == 2 and measured[8][0] == 1, measured
    assert measured[1][1] > measured[8][1], f'the case this is about did not arise: {measured}'

    chosen = answer['fits']['sheet']
    assert (chosen['every'], chosen['picture'], chosen['pages']) == (8, 44.0, 1), chosen


def test_a_summary_encoded_twice_prints_nothing_rather_than_its_codes(digest):
    """ROB tv encodes twice: a summary of three spaces arrives as `&amp;nbsp;` three times,
    which reads once as `&nbsp;` — and that is what the sheet would have printed."""
    summary = recorded_summary('robtv.xml', 'Nieuws donderdag 17 september')
    assert '&amp;nbsp;' in summary, 'the fixture no longer carries what this is about'

    answer = built(digest(news={'many': 4, 'summary': summary}))(
        intro='Encoded.',
        picks=[pick(0)],
        more=[{'id': 'vrt-2026-09-15-story-1-and-what-came-of-it', 'topic': 'regional'}],
    )

    prose = text_of(answer['page']['path'])
    assert 'nbsp' not in prose and '&' not in prose, 'a character code reached the page'


@respx.mock
def test_a_picture_that_will_not_come_is_asked_for_once_per_build(digest):
    """The sheet is rendered once per setting on the ladder. A failed picture that is not
    remembered is asked for again every time, each for up to fifteen seconds."""
    dead = respx.get('https://pictures.test/0.jpg').mock(return_value=httpx.Response(404))
    answer = built(digest(news={'many': 8, 'image': 'https://pictures.test/0.jpg'}))(
        intro='No pictures.',
        picks=[pick(0)],
        more=[{'id': f'vrt-2026-09-15-story-{n}-and-what-came-of-it', 'topic': 'world'} for n in range(1, 6)],
    )

    assert dead.call_count == 1, f'one dead address was asked for {dead.call_count} times'
    assert answer['page']['crowded'] == []


def test_the_brief_lets_a_category_have_what_the_day_has():
    """The sheet has no sections, so nothing looks broken with one story in it — and the brief
    stops asking Claude to bend the news to the layout."""
    brief = ' '.join((REPO / '.harry' / 'jobs' / 'morning-page' / 'JOB.md').read_text(encoding='utf-8').split())

    assert 'about four in each category' not in brief.lower()
    assert 'looks broken' not in brief
    assert 'A category gets what the day has' in brief
