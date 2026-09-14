"""The two tools Claude reaches — the headlines, and the text of one of them.

They stay apart on purpose: choosing among forty headlines is the product, not overhead.
Every call here goes through the MCP server the way a session does, because a tool tested
by calling the connector behind it proves nothing about the tool.

**No test here reaches bbc.co.uk or vrt.be.** The feeds and both article pages are recorded
in `tests/fixtures/news/`.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import httpx
import pytest
import respx
from fastmcp import Client

from harry.alerts import Alerts
from harry.loader import load
from harry.mcp import FIND_TOOLS, build_server
from harry.store import Store

REPO = Path(__file__).parent.parent
FIXTURES = Path(__file__).parent / 'fixtures' / 'news'

VRT = 'https://www.vrt.be/vrtnws/nl.rss.articles.xml'
BBC = 'https://feeds.bbci.co.uk/news/rss.xml'

TRAIN = 'https://www.bbc.co.uk/news/articles/cy5zg41dkqwo'
"""The BBC story whose page is recorded as `bbc-article.html`."""

TRAIN_ID = 'bbc-2026-09-14-russia-hits-ukrainian-train-shortly'

SHORT_VRT_LINK = 'https://vrtnws.be/p.oL1bKEomY'
LONG_VRT_LINK = (
    'https://www.vrt.be/vrtnws/nl/2026/09/12/tessenderlo-ham-beslist-vanaf-1-januari-2027-brengt-ocmw-niet-l/'
)
OCMW_ID = 'vrt-2026-09-14-tessenderlo-ham-hakt-knoop-door'


def recorded(name: str) -> str:
    return (FIXTURES / name).read_text(encoding='utf-8')


class Somewhere:
    def __init__(self) -> None:
        self.heard: list[str] = []

    def __call__(self, message: str) -> None:
        self.heard.append(message)


@pytest.fixture
def harry(tmp_path, monkeypatch):
    """The news connector and both its tools, behind a real MCP server."""
    for key in ('FEEDS', 'TIMEZONE'):
        monkeypatch.delenv(f'HARRY_NEWS_{key}', raising=False)

    def build():
        root = tmp_path / 'root'
        for where in ('connectors/news', 'tools/news_search', 'tools/news_article'):
            (root / where).parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(REPO / '.harry' / where, root / where, dirs_exist_ok=True)

        alerts = Alerts()
        catalogue = load([root], alerts=alerts)
        alerts.attach(catalogue)
        sink = Somewhere()
        alerts._sinks = [sink]  # noqa: SLF001 — no Slack connector in this root to take them
        return build_server(catalogue, Store(tmp_path / 'jobs.json')), sink

    return build


def feeds_are_up():
    respx.get(VRT).mock(return_value=httpx.Response(200, text=recorded('vrt-nws.xml')))
    respx.get(BBC).mock(return_value=httpx.Response(200, text=recorded('bbc-news.xml')))


async def found_through(connected, name: str, arguments: dict | None = None):
    """Find the tool the way a session does, then call it."""
    await connected.call_tool(FIND_TOOLS, {'query': 'news'})
    return await connected.call_tool(name, arguments or {})


# ---------------------------------------------------------------------------
# Both tools are on the roster, and neither is loaded until asked for
# ---------------------------------------------------------------------------


@respx.mock
async def test_both_tools_defer_and_are_found_by_search(harry):
    feeds_are_up()
    server, _ = harry()

    async with Client(server) as connected:
        loaded = [tool.name for tool in await connected.list_tools()]
        assert 'news_search' not in loaded and 'news_article' not in loaded, 'both should defer'

        found = (await connected.call_tool(FIND_TOOLS, {'query': 'news'})).data
        assert sorted(row['name'] for row in found['found']) == ['news_article', 'news_search']


@respx.mock
async def test_both_tools_are_read_only(harry):
    """This is how a client can let `news_search` through without letting a write through."""
    feeds_are_up()
    server, _ = harry()

    async with Client(server) as connected:
        await connected.call_tool(FIND_TOOLS, {'query': 'news'})
        published = {tool.name: tool for tool in await connected.list_tools()}

    for name in ('news_search', 'news_article'):
        hints = published[name].annotations
        assert hints is not None, f'{name} published no annotations at all'
        assert hints.read_only_hint is True


def test_the_connector_lists_both_tools_in_provides():
    """Exposure is a choice the connector makes, not something a tool folder can claim."""
    declaration = (REPO / '.harry' / 'connectors' / 'news' / 'CONNECTOR.md').read_text(encoding='utf-8')

    assert 'provides: [news_search, news_article]' in declaration


# ---------------------------------------------------------------------------
# news_search
# ---------------------------------------------------------------------------


@respx.mock
async def test_search_returns_the_twenty_newest(harry):
    feeds_are_up()
    server, _ = harry()

    async with Client(server) as connected:
        answer = (await found_through(connected, 'news_search')).data

    assert len(answer['candidates']) == 16, 'the fixtures carry 16 between them, under the cap'
    dates = [candidate['date'] for candidate in answer['candidates']]
    assert dates == sorted(dates, reverse=True)
    assert answer['unavailable'] == []


@respx.mock
async def test_search_never_returns_more_than_fifty(harry):
    """Forty is what the morning page chooses from. Fifty is the ceiling."""
    many = recorded('bbc-news.xml')
    one_item = '<item>' + many.split('<item>', 1)[1].split('</item>')[0] + '</item>'
    stuffed = (
        many.split('<item>')[0]
        + ''.join(
            one_item.replace('cy5zg41dkqwo', f'story{n:03d}').replace('<title>', f'<title>Story number {n} ')
            for n in range(60)
        )
        + '</channel></rss>'
    )
    respx.get(BBC).mock(return_value=httpx.Response(200, text=stuffed))
    respx.get(VRT).mock(return_value=httpx.Response(200, text=recorded('vrt-nws.xml')))
    server, _ = harry()

    async with Client(server) as connected:
        answer = (await found_through(connected, 'news_search', {'limit': 100})).data

    assert len(answer['candidates']) == 50


@respx.mock
async def test_search_narrows_by_source(harry):
    feeds_are_up()
    server, _ = harry()

    async with Client(server) as connected:
        answer = (await found_through(connected, 'news_search', {'source': 'bbc'})).data

    assert len(answer['candidates']) == 8
    assert {candidate['source'] for candidate in answer['candidates']} == {'BBC News'}


@respx.mock
async def test_search_narrows_by_date(harry):
    """`vrt-nws.xml` carries one story from April among seven from September, so there is
    something real for this to exclude."""
    feeds_are_up()
    server, _ = harry()

    async with Client(server) as connected:
        everything = (await found_through(connected, 'news_search', {'source': 'vrt'})).data
        recent = (await found_through(connected, 'news_search', {'source': 'vrt', 'since': '2026-09-01'})).data

    assert '2026-04-20' in [candidate['date'] for candidate in everything['candidates']]
    assert len(recent['candidates']) == len(everything['candidates']) - 1
    assert all(candidate['date'] >= '2026-09-01' for candidate in recent['candidates'])


@respx.mock
async def test_search_narrows_by_query(harry):
    feeds_are_up()
    server, _ = harry()

    async with Client(server) as connected:
        answer = (await found_through(connected, 'news_search', {'query': 'TRAIN'})).data

    assert answer['candidates'], 'the recorded BBC feed carries two train stories'
    for candidate in answer['candidates']:
        assert 'train' in f'{candidate["title"]} {candidate["summary"]}'.lower()


@respx.mock
async def test_concise_is_the_default_and_costs_less(harry):
    """Twenty summaries land in the caller's context on every call. Two hundred characters
    is enough to tell what a story is about, which is all a candidate is for."""
    feeds_are_up()
    server, _ = harry()

    async with Client(server) as connected:
        concise = (await found_through(connected, 'news_search')).data
        full = (await found_through(connected, 'news_search', {'detail': 'full'})).data

    trimmed = next(candidate for candidate in concise['candidates'] if candidate['summary'].endswith('…'))
    assert len(trimmed['summary']) == 201, '200 characters and the ellipsis'
    assert set(trimmed) == {'id', 'title', 'source', 'feed', 'date', 'summary'}

    same = next(candidate for candidate in full['candidates'] if candidate['id'] == trimmed['id'])
    assert len(same['summary']) > len(trimmed['summary'])
    assert same['link'] and same['published']


@respx.mock
async def test_a_dead_feed_is_visible_to_claude_as_well_as_in_slack(harry):
    """A shorter list on its own says nothing. If `unavailable` is empty when a feed is
    down, Claude reports a quiet news day."""
    respx.get(BBC).mock(return_value=httpx.Response(200, text=recorded('bbc-news.xml')))
    respx.get(VRT).mock(return_value=httpx.Response(404))
    server, sink = harry()

    async with Client(server) as connected:
        answer = (await found_through(connected, 'news_search')).data

    assert len(answer['candidates']) == 8
    assert answer['unavailable'] == [{'source': 'VRT NWS', 'why': 'VRT NWS answered 404'}]
    assert sink.heard == ['VRT NWS: VRT NWS answered 404']


# ---------------------------------------------------------------------------
# news_article
# ---------------------------------------------------------------------------


@respx.mock
async def test_an_article_comes_back_as_prose(harry):
    feeds_are_up()
    respx.get(url__startswith=TRAIN).mock(return_value=httpx.Response(200, text=recorded('bbc-article.html')))
    server, _ = harry()

    async with Client(server) as connected:
        answer = (await found_through(connected, 'news_article', {'id': TRAIN_ID})).data

    assert answer['available'] is True
    assert answer['title'].startswith('Russia hits Ukrainian train')
    assert answer['source'] == 'BBC News'
    assert answer['published'] == '2026-09-14T03:38:13+00:00'
    assert len(answer['text']) > 1000
    assert 'A Russian drone has hit a train near the Ukraine-Poland border' in answer['text']


@respx.mock
async def test_the_navigation_and_the_furniture_are_left_behind(harry):
    """The recorded page is 430 KB. What comes back is the article."""
    feeds_are_up()
    respx.get(url__startswith=TRAIN).mock(return_value=httpx.Response(200, text=recorded('bbc-article.html')))
    server, _ = harry()

    async with Client(server) as connected:
        text = (await found_through(connected, 'news_article', {'id': TRAIN_ID})).data['text']

    assert len(text) < len(recorded('bbc-article.html')) / 20
    assert '<div' not in text and 'BBC iPlayer' not in text


@respx.mock
async def test_the_page_is_asked_for_as_a_browser_and_the_redirect_is_followed(harry):
    """VRT's feed links are short `vrtnws.be/p.…` URLs that redirect, and news sites serve
    a consent wall to anything that does not look like a browser."""
    feeds_are_up()
    respx.get(SHORT_VRT_LINK).mock(return_value=httpx.Response(301, headers={'Location': LONG_VRT_LINK}))
    landed = respx.get(LONG_VRT_LINK).mock(return_value=httpx.Response(200, text=recorded('vrt-article.html')))
    server, _ = harry()

    async with Client(server) as connected:
        answer = (await found_through(connected, 'news_article', {'id': OCMW_ID})).data

    assert answer['available'] is True
    assert 'Het OCMW van Tessenderlo-Ham' in answer['text']
    assert 'Mozilla/5.0' in landed.calls[0].request.headers['user-agent']


@respx.mock
async def test_an_id_no_feed_carries_says_to_search_again(harry):
    """The caller's mistake, so it raises. `news_search` has moved on; that is not a fault
    to report, it is a thing to do again."""
    feeds_are_up()
    server, _ = harry()

    async with Client(server) as connected:
        await connected.call_tool(FIND_TOOLS, {'query': 'news'})
        result = await connected.call_tool(
            'news_article', {'id': 'bbc-2026-01-01-a-story-that-never-was'}, raise_on_error=False
        )

    assert result.is_error is True
    said = str(result.content[0].text)  # type: ignore[union-attr]
    assert 'bbc-2026-01-01-a-story-that-never-was' in said
    assert 'news_search again' in said


@respx.mock
async def test_a_page_that_blocks_us_is_an_answer_not_an_error(harry):
    """A tool that raises tells the model it did something wrong, and it did not. There is
    nothing to retry and the headline is still true."""
    feeds_are_up()
    respx.get(url__startswith=TRAIN).mock(return_value=httpx.Response(403, text='<html>no bots</html>'))
    server, sink = harry()

    async with Client(server) as connected:
        await connected.call_tool(FIND_TOOLS, {'query': 'news'})
        result = await connected.call_tool('news_article', {'id': TRAIN_ID}, raise_on_error=False)

    assert result.is_error is False, 'a blocked page is information'
    assert result.data['available'] is False
    assert result.data['why'] == 'BBC News answered 403'
    assert result.data['title'].startswith('Russia hits Ukrainian train'), 'the headline survives'
    assert 'text' not in result.data
    assert sink.heard == ['BBC News: BBC News answered 403']


@respx.mock
async def test_a_page_with_no_prose_in_it_says_so(harry):
    """Usually a video or a live blog. The id resolves, the page loads, there is nothing to
    read — and that has to be distinguishable from a page that failed to load."""
    feeds_are_up()
    respx.get(url__startswith=TRAIN).mock(
        return_value=httpx.Response(200, text='<html><body><nav>Home</nav><p>Watch</p></body></html>')
    )
    server, sink = harry()

    async with Client(server) as connected:
        answer = (await found_through(connected, 'news_article', {'id': TRAIN_ID})).data

    assert answer['available'] is False
    assert answer['why'] == 'the page loaded but there was no article text in it'
    assert sink.heard == ['BBC News: the page loaded but there was no article text in it']


@respx.mock
async def test_one_search_and_three_reads_download_each_feed_once(harry):
    """Every `news_article` re-resolves its id against the feeds, which is what lets the
    digest hold nothing between its two calls. Without the 5-minute reuse that is eight
    downloads of the same two documents."""
    feeds_are_up()
    respx.get(url__startswith=TRAIN).mock(return_value=httpx.Response(200, text=recorded('bbc-article.html')))
    server, _ = harry()

    async with Client(server) as connected:
        await found_through(connected, 'news_search')
        for _ in range(3):
            await connected.call_tool('news_article', {'id': TRAIN_ID})

    assert respx.get(VRT).call_count == 1
    assert respx.get(BBC).call_count == 1
    assert respx.get(url__startswith=TRAIN).call_count == 3, 'each article is still fetched'
