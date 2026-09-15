"""The morning page, built from what Claude chose.

Loaded, not imported: `pyproject.toml` keeps `.harry` off pytest's path, so a test cannot
reach the tool directly and pass while the loader is broken.

**No test here reaches a network.** The connectors are stand-ins steered by a plan file, and
the one picture a test uses is served by respx. What matters here is the shape of the paper —
what goes where, in which order, and what happens when a piece of it is missing.
"""

from __future__ import annotations

import json
from pathlib import Path

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
    name. Four settings and one silence worth naming."""
    prose = ' '.join((REPO / 'docs' / 'morning-page.md').read_text(encoding='utf-8').split())
    index = (REPO / 'docs' / 'index.md').read_text(encoding='utf-8')

    assert 'morning-page.md' in index, 'a page nobody links to is a page nobody reads'
    for setting in ('NAME', 'COLOURS', 'OUT_DIR', 'TIMEZONE'):
        assert setting in prose, f'{setting} is not documented'
    assert 'make digest-dry PICKS=picks.json' in prose
    assert 'morning-page has not run today' in prose, 'the one failure with no other trace'
    assert 'the columns are local' in prose
    assert 'silent correction is how the wrong story gets printed' in prose
