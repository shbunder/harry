"""Two feeds in, one list of candidates out — and what happens when a feed dies.

Loaded, not imported: `pyproject.toml` keeps `.harry` off pytest's path, so these copy the
real folder into a temporary root and run it through `load()`. A test that reached the
connector directly would pass while the loader was broken.

**No test here reaches vrt.be or bbci.co.uk.** Every feed is a document recorded on
14 September 2026 and kept in `tests/fixtures/news/`, which has a README saying what was
trimmed out of each one. The failures are respx side-effects over those same URLs.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest
import respx

from harry.alerts import Alerts
from harry.loader import load

from .capability_copy import copy_capability

REPO = Path(__file__).parent.parent
FIXTURES = Path(__file__).parent / 'fixtures' / 'news'

VRT = 'https://www.vrt.be/vrtnws/nl.rss.articles.xml'
BBC = 'https://feeds.bbci.co.uk/news/rss.xml'
WORLD = 'https://feeds.bbci.co.uk/news/world/rss.xml'

THREE_FEEDS = f'FEEDS=vrt=VRT NWS={VRT}|bbc=BBC News={BBC}|world=BBC World={WORLD}\n'

BOTH_BBC_FEEDS = 'https://www.bbc.co.uk/news/videos/cx2z5gjj838o'
"""The story `bbc-news.xml` and `bbc-world.xml` both carry, under two different headlines.
Deduplicating on the headline would keep both, which is why it is the one used here."""


def recorded(name: str) -> str:
    return (FIXTURES / name).read_text(encoding='utf-8')


class Somewhere:
    """A sink that remembers what it was told."""

    def __init__(self) -> None:
        self.heard: list[str] = []

    def __call__(self, message: str) -> None:
        self.heard.append(message)


@pytest.fixture
def news(tmp_path, monkeypatch):
    """The real `.harry/connectors/news/`, loaded, with somewhere for its alerts to land."""
    for key in ('FEEDS', 'TIMEZONE'):
        monkeypatch.delenv(f'HARRY_NEWS_{key}', raising=False)

    def build(*, settings: str = '', tools: tuple[str, ...] = ()):
        root = tmp_path / 'root'
        for where in ('connectors/news', *(f'tools/{tool}' for tool in tools)):
            (root / where).parent.mkdir(parents=True, exist_ok=True)
            copy_capability(REPO / '.harry' / where, root / where)
        if settings:
            (root / 'connectors' / 'news' / '.env.local').write_text(settings, encoding='utf-8')

        alerts = Alerts()
        catalogue = load([root], alerts=alerts)
        alerts.attach(catalogue)
        sink = Somewhere()
        alerts._sinks = [sink]  # noqa: SLF001 — no Slack connector in this root to take them
        return catalogue, sink

    return build


def connector(built):
    catalogue, _ = built
    found = catalogue.get('connector', 'news')
    assert found is not None and found.target is not None, [f'{c.name}: {c.reason}' for c in catalogue.skipped]
    return found.target


def serving(**documents: str):
    """Point each feed URL at a recorded document."""
    for url, name in documents.items():
        respx.get(url).mock(return_value=httpx.Response(200, text=recorded(name)))


def both_feeds():
    serving(**{VRT: 'vrt-nws.xml', BBC: 'bbc-news.xml'})


# ---------------------------------------------------------------------------
# Two formats, one shape
# ---------------------------------------------------------------------------


@respx.mock
def test_an_atom_feed_becomes_candidates(news):
    """VRT NWS is Atom — a namespaced <feed> of <entry>. A parser written for RSS alone
    reads this document without error and returns nothing at all."""
    serving(**{VRT: 'vrt-nws.xml', BBC: 'bbc-news.xml'})

    found = [c for c in connector(news()).candidates(50) if c['feed'] == 'vrt']

    assert len(found) == 8
    first = next(c for c in found if c['title'].startswith('Tessenderlo-Ham'))
    assert first['source'] == 'VRT NWS'
    assert first['published'] == '2026-09-14T09:05:56+00:00'
    assert first['summary'].startswith('Het OCMW van Tessenderlo-Ham')
    assert first['link'] == 'https://vrtnws.be/p.oL1bKEomY'


@respx.mock
def test_an_rss_feed_becomes_the_same_shape(news):
    """BBC News is RSS 2.0 — a <channel> of <item>, no namespace."""
    both_feeds()

    found = [c for c in connector(news()).candidates(50) if c['feed'] == 'bbc']

    assert len(found) == 8
    first = next(c for c in found if c['title'].startswith('Russia hits Ukrainian train'))
    assert first['source'] == 'BBC News'
    assert first['published'] == '2026-09-14T03:38:13+00:00'
    assert first['summary'].startswith('The former UK PM said')
    assert first['link'].startswith('https://www.bbc.co.uk/news/articles/cy5zg41dkqwo')


@respx.mock
def test_every_candidate_carries_the_five_fields_the_digest_asked_for(news):
    """The morning page wrote this shape down before any source existed, so that each
    source had something to satisfy rather than an interface invented when the page finally
    called it. Dropping a field here breaks a caller that is not written yet."""
    both_feeds()

    for candidate in connector(news()).candidates(50):
        assert set(candidate) >= {'id', 'title', 'source', 'published', 'summary', 'link'}
        assert candidate['title'] and candidate['link']


@respx.mock
def test_the_vrt_link_is_the_alternate_one(news):
    """Each VRT entry has three links. `rel="self"` looks like the obvious one and is a
    per-article `.rss.xml` document — the entry again, not the article."""
    both_feeds()

    links = [c['link'] for c in connector(news()).candidates(50) if c['feed'] == 'vrt']

    assert all(link.startswith('https://vrtnws.be/p.') for link in links), links
    assert not any(link.endswith('.rss.xml') for link in links)


@respx.mock
def test_a_feed_that_is_xml_but_not_a_feed_says_which_root_it_had(news):
    serving(**{BBC: 'bbc-news.xml'})
    respx.get(VRT).mock(return_value=httpx.Response(200, text='<opml version="2.0"><body/></opml>'))

    _, unavailable = connector(news()).search()['candidates'], connector(news()).search()['unavailable']

    assert unavailable == [{'source': 'VRT NWS', 'why': 'the document is XML but not a feed (its root is <opml>)'}]


# ---------------------------------------------------------------------------
# Ids you can read
# ---------------------------------------------------------------------------


@respx.mock
def test_an_id_is_the_feed_the_date_and_five_words(news):
    both_feeds()

    found = connector(news()).candidates(50)

    assert 'vrt-2026-09-14-tessenderlo-ham-hakt-knoop-door' in [c['id'] for c in found]
    assert 'bbc-2026-09-14-russia-hits-ukrainian-train-shortly' in [c['id'] for c in found]


@respx.mock
def test_accents_are_folded_out_of_an_id(news):
    """ "Tsjechië" has to survive into a URL-safe id without becoming unreadable."""
    both_feeds()

    found = next(c for c in connector(news()).candidates(50) if 'Tsjechi' in c['title'])

    assert found['id'] == 'vrt-2026-09-14-brandstichtingen-in-polen-tsjechie-en'


@respx.mock
def test_two_stories_that_start_alike_still_get_one_id_each(news):
    """`collision.xml` is three NMBS strike stories from one feed on one day whose first
    five title words are identical."""
    respx.get(VRT).mock(return_value=httpx.Response(200, text=recorded('collision.xml')))
    serving(**{BBC: 'bbc-news.xml'})

    ids = [c['id'] for c in connector(news()).candidates(50) if c['feed'] == 'vrt']

    assert sorted(ids) == [
        'vrt-2026-09-14-staking-bij-de-nmbs-legt',
        'vrt-2026-09-14-staking-bij-de-nmbs-legt-2',
        'vrt-2026-09-14-staking-bij-de-nmbs-legt-3',
    ]
    assert len(set(ids)) == 3, 'three stories, three ids'


@respx.mock
def test_a_story_published_late_in_utc_is_filed_the_next_day(news):
    """The third entry in `collision.xml` is published 22:30 UTC, which is 00:30 the next
    morning in Brussels. The id says the day you would have read it."""
    respx.get(VRT).mock(return_value=httpx.Response(200, text=recorded('collision.xml')))
    serving(**{BBC: 'bbc-news.xml'})

    late = next(c for c in connector(news()).candidates(50) if c['title'].endswith('aan de kust'))

    assert late['published'] == '2026-09-13T22:30:00+00:00'
    assert late['date'] == '2026-09-14'
    assert late['id'].startswith('vrt-2026-09-14-')


@respx.mock
def test_a_different_zone_files_it_a_different_day(news):
    """Delete the timezone and this story lands on the 13th, where nobody would look."""
    respx.get(VRT).mock(return_value=httpx.Response(200, text=recorded('collision.xml')))
    serving(**{BBC: 'bbc-news.xml'})

    built = news(settings=f'TIMEZONE=UTC\n{THREE_FEEDS.replace("|world=BBC World=" + WORLD, "")}')
    respx.get(WORLD).mock(return_value=httpx.Response(200, text=recorded('bbc-world.xml')))
    late = next(c for c in connector(built).candidates(50) if c['title'].endswith('aan de kust'))

    assert late['date'] == '2026-09-13'


def test_a_zone_that_does_not_exist_falls_back_to_utc(news, caplog):
    with caplog.at_level(logging.WARNING, logger='harry.capability.news'):
        built = news(settings='TIMEZONE=Mars/Olympus_Mons\n')

    assert connector(built) is not None, 'a bad zone must not take the connector down'
    assert 'no zone called' in caplog.text


# ---------------------------------------------------------------------------
# One story, once
# ---------------------------------------------------------------------------


@respx.mock
def test_one_story_in_two_feeds_is_one_candidate(news):
    """Both BBC feeds carry cx2z5gjj838o under different headlines. Deduplicating on the
    headline would keep both."""
    serving(**{VRT: 'vrt-nws.xml', BBC: 'bbc-news.xml', WORLD: 'bbc-world.xml'})

    found = connector(news(settings=THREE_FEEDS)).candidates(50)

    carrying = [c for c in found if c['link'].startswith(BOTH_BBC_FEEDS)]
    assert len(carrying) == 1, [c['title'] for c in carrying]


@respx.mock
def test_the_feed_listed_first_keeps_the_duplicate(news):
    """Which copy you get is a decision somebody made in FEEDS, not a race between two
    downloads."""
    serving(**{VRT: 'vrt-nws.xml', BBC: 'bbc-news.xml', WORLD: 'bbc-world.xml'})

    found = connector(news(settings=THREE_FEEDS)).candidates(50)
    kept = next(c for c in found if c['link'].startswith(BOTH_BBC_FEEDS))

    assert kept['source'] == 'BBC News'
    assert kept['title'] == 'Watch: Why Russian strike on train could be sign of escalation'

    reversed_order = THREE_FEEDS.replace(
        f'bbc=BBC News={BBC}|world=BBC World={WORLD}', f'world=BBC World={WORLD}|bbc=BBC News={BBC}'
    )
    found = connector(news(settings=reversed_order)).candidates(50)
    kept = next(c for c in found if c['link'].startswith(BOTH_BBC_FEEDS))

    assert kept['source'] == 'BBC World'
    assert kept['title'].startswith('Watch: Why a Russian strike on train near Ukraine-Poland')


@respx.mock
def test_four_shared_stories_come_back_once_each(news):
    serving(**{BBC: 'bbc-news.xml', WORLD: 'bbc-world.xml'})

    found = connector(news(settings=f'FEEDS=bbc=BBC News={BBC}|world=BBC World={WORLD}\n')).candidates(50)

    assert len(found) == 12, '8 + 8 with 4 carried by both'


@respx.mock
def test_the_tracking_on_a_link_is_not_part_of_which_story_it_is(news):
    """The BBC's feed links carry `?at_medium=RSS` and its guids carry `#0`. Both point at
    the same article."""
    plain = 'https://www.bbc.co.uk/news/articles/cy5zg41dkqwo'
    twice = f"""<rss version="2.0"><channel><title>Somewhere</title>
      <item><title>A story</title><description>x</description>
        <link>{plain}?at_medium=RSS&amp;at_campaign=rss</link>
        <pubDate>Mon, 14 Sep 2026 03:38:13 GMT</pubDate></item>
      <item><title>The same story again</title><description>x</description>
        <link>{plain}#0</link>
        <pubDate>Mon, 14 Sep 2026 03:38:13 GMT</pubDate></item>
    </channel></rss>"""
    respx.get(BBC).mock(return_value=httpx.Response(200, text=twice))
    serving(**{VRT: 'vrt-nws.xml'})

    found = [c for c in connector(news()).candidates(50) if c['feed'] == 'bbc']

    assert len(found) == 1
    assert found[0]['title'] == 'A story', 'the first one wins, as with any duplicate'


@respx.mock
def test_candidates_come_back_newest_first(news):
    both_feeds()

    published = [c['published'] for c in connector(news()).candidates(50)]

    assert published == sorted(published, reverse=True)


# ---------------------------------------------------------------------------
# Configuring the feeds
# ---------------------------------------------------------------------------


@respx.mock
def test_feeds_is_slug_name_url_separated_by_pipes(news):
    serving(**{VRT: 'vrt-nws.xml', BBC: 'bbc-news.xml', WORLD: 'bbc-world.xml'})

    found = connector(news(settings=THREE_FEEDS)).candidates(50)

    assert {c['feed'] for c in found} == {'vrt', 'bbc', 'world'}
    assert {c['source'] for c in found} == {'VRT NWS', 'BBC News', 'BBC World'}


@respx.mock
def test_a_url_may_carry_as_many_more_equals_signs_as_it_likes(news):
    """Split on the first two, not on every one."""
    awkward = 'https://example.test/rss?format=xml&lang=nl'
    respx.get(awkward).mock(return_value=httpx.Response(200, text=recorded('bbc-news.xml')))

    found = connector(news(settings=f'FEEDS=odd=Odd One={awkward}\n')).candidates(50)

    assert len(found) == 8
    assert found[0]['source'] == 'Odd One'


@respx.mock
def test_a_malformed_feeds_entry_costs_one_feed(news, caplog):
    broken = f'FEEDS=vrt=VRT NWS={VRT}|bbchttps://feeds.bbci.co.uk/news/rss.xml\n'
    serving(**{VRT: 'vrt-nws.xml'})

    with caplog.at_level(logging.WARNING, logger='harry.capability.news'):
        found = connector(news(settings=broken)).candidates(50)

    assert len(found) == 8, 'VRT NWS still loaded'
    assert 'not slug=Name=url' in caplog.text


def test_a_feeds_setting_with_nothing_usable_in_it_skips_the_connector(news):
    """A news source with nothing to read is misconfigured, not degraded. Loading it would
    give a page an empty news section with no reason anywhere.

    `FEEDS=` on its own cannot get here: core reads an empty value as an unset key, so the
    declaration's default applies. This is the reachable version — a setting somebody typed
    that parses to no feeds at all.
    """
    catalogue, _ = news(settings='FEEDS=https://feeds.bbci.co.uk/news/rss.xml\n')

    found = catalogue.get('connector', 'news')
    assert found is not None and found.target is None, 'it must not load with nothing to read'
    assert any('FEEDS is empty' in (c.reason or '') for c in catalogue.skipped), [c.reason for c in catalogue.skipped]


def test_the_committed_env_ships_both_feeds():
    """A default nobody has to set is one fewer thing between a fresh clone and a page.
    Neither URL is a secret, so the committed file carries the real ones."""
    committed = (REPO / '.harry' / 'connectors' / 'news' / '.env').read_text(encoding='utf-8')
    values = dict(line.split('=', 1) for line in committed.splitlines() if line and not line.startswith('#'))

    assert values['FEEDS'] == f'vrt=VRT NWS={VRT}|bbc=BBC News={BBC}'
    assert values['TIMEZONE'] == 'Europe/Brussels'


# ---------------------------------------------------------------------------
# A dead feed costs one source, and says so
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ('failure', 'why'),
    [
        (lambda _: httpx.Response(404, text='<html><body>gone</body></html>'), 'VRT NWS answered 404'),
        (lambda _: httpx.Response(500, text='upstream is unhappy'), 'VRT NWS answered 500'),
        (httpx.ConnectError('no route to host'), 'VRT NWS could not be reached'),
        (httpx.ReadTimeout('too slow'), 'VRT NWS did not answer within 10s'),
    ],
)
@respx.mock
def test_a_dead_feed_leaves_the_others_alone_and_says_why(news, failure, why, caplog):
    serving(**{BBC: 'bbc-news.xml'})
    route = respx.get(VRT).mock(side_effect=failure)
    built = news()

    with caplog.at_level(logging.WARNING, logger='harry.capability.news'):
        answer = connector(built).search(limit=50)

    assert len(answer['candidates']) == 8, 'BBC News still came back'
    assert answer['unavailable'] == [{'source': 'VRT NWS', 'why': why}]
    assert route.call_count == 1, 'one attempt — a retry loop would double the page build'
    assert 'VRT NWS is unavailable' in caplog.text


@respx.mock
def test_a_dead_feed_puts_one_line_in_slack(news):
    """The reason this feature exists. A shorter headline list looks exactly like a quiet
    news day, so Slack is the only thing that tells the difference."""
    serving(**{BBC: 'bbc-news.xml'})
    respx.get(VRT).mock(return_value=httpx.Response(404))
    built = news()

    connector(built).candidates(50)

    _, sink = built
    assert sink.heard == ['VRT NWS: VRT NWS answered 404']


@respx.mock
def test_the_slack_line_carries_no_url_and_nothing_from_the_body(news):
    """A feed URL can carry a key in its query string, and a 404 body is somebody else's
    HTML. Neither belongs in a message a person reads."""
    serving(**{BBC: 'bbc-news.xml'})
    respx.get(VRT).mock(return_value=httpx.Response(404, text='<html>Not found: token=sekrit</html>'))
    built = news()

    connector(built).candidates(50)

    _, sink = built
    assert len(sink.heard) == 1
    assert 'vrt.be' not in sink.heard[0]
    assert 'sekrit' not in sink.heard[0] and 'html' not in sink.heard[0]


@respx.mock
def test_a_feed_that_already_failed_today_is_silent(news):
    """Keyed on the feed, so a source down all week is one line a day rather than one every
    five minutes."""
    serving(**{BBC: 'bbc-news.xml'})
    respx.get(VRT).mock(return_value=httpx.Response(404))
    built = news()
    reader = connector(built)

    reader.candidates(50)
    reader._cached.clear()  # noqa: SLF001 — otherwise the second call never reaches the feed
    reader.candidates(50)

    _, sink = built
    assert sink.heard == ['VRT NWS: VRT NWS answered 404'], 'said once, not twice'


@respx.mock
def test_each_feed_gets_its_own_alert(news):
    """Two dead feeds are two faults, not one."""
    respx.get(VRT).mock(return_value=httpx.Response(404))
    respx.get(BBC).mock(return_value=httpx.Response(503))
    built = news()

    answer = connector(built).search(limit=50)

    assert answer['candidates'] == []
    assert [row['source'] for row in answer['unavailable']] == ['VRT NWS', 'BBC News']
    _, sink = built
    assert sink.heard == ['VRT NWS: VRT NWS answered 404', 'BBC News: BBC News answered 503']


@respx.mock
def test_html_where_a_feed_was_expected_is_one_unavailable_source(news):
    """A feed URL that has quietly become a web page — a consent wall, an error page."""
    serving(**{BBC: 'bbc-news.xml'})
    respx.get(VRT).mock(return_value=httpx.Response(200, text=recorded('not-a-feed.html')))
    built = news()

    answer = connector(built).search(limit=50)

    assert len(answer['candidates']) == 8
    assert answer['unavailable'][0]['source'] == 'VRT NWS'
    assert 'not XML' in answer['unavailable'][0]['why']


@respx.mock
def test_a_feed_declaring_its_own_entities_is_refused_unread(news):
    """`bomb.xml` is 800 bytes that expand to gigabytes. ElementTree will do it — it is
    only external entities it refuses — so the document has to be turned away first."""
    serving(**{BBC: 'bbc-news.xml'})
    respx.get(VRT).mock(return_value=httpx.Response(200, text=recorded('bomb.xml')))
    built = news()

    answer = connector(built).search(limit=50)

    assert len(answer['candidates']) == 8, 'BBC News still came back'
    assert answer['unavailable'] == [
        {'source': 'VRT NWS', 'why': 'the document declares its own entities, which a feed has no reason to do'}
    ]


def test_the_bomb_fixture_really_is_one():
    """If the standard library ever starts refusing this on its own, the guard above stops
    proving anything — and this test is what says so."""
    import xml.etree.ElementTree as ElementTree

    root = ElementTree.fromstring(recorded('bomb.xml').replace('&lol9;', '&lol4;'))

    assert len(root.findtext('.//title') or '') == 30_000, 'four levels already. There are nine'


@respx.mock
def test_a_plain_html_doctype_is_not_what_the_refusal_is_for(news):
    """`<!doctype html>` declares nothing. An HTML page served where a feed was expected
    should fail as "this is not XML", which is the reason a person can act on."""
    serving(**{BBC: 'bbc-news.xml'})
    respx.get(VRT).mock(return_value=httpx.Response(200, text=recorded('not-a-feed.html')))

    why = connector(news()).search()['unavailable'][0]['why']

    assert 'entities' not in why


@respx.mock
def test_every_feed_down_is_an_empty_list_not_an_exception(news):
    """The morning page has to render. An empty news section is a section; a traceback
    halfway through building a PDF is not."""
    respx.get(VRT).mock(side_effect=httpx.ConnectError('nope'))
    respx.get(BBC).mock(side_effect=httpx.ConnectError('nope'))

    assert connector(news()).candidates(50) == []


@respx.mock
def test_candidates_stays_a_plain_list(news):
    """It cannot say a feed died and it is not asked to — the page hears that from Slack.
    A list that sometimes returned a dict would be two shapes nobody could rely on."""
    serving(**{BBC: 'bbc-news.xml'})
    respx.get(VRT).mock(return_value=httpx.Response(404))

    found = connector(news()).candidates(50)

    assert isinstance(found, list)
    assert all(isinstance(candidate, dict) and 'unavailable' not in candidate for candidate in found)


def test_the_feed_call_carries_a_ten_second_ceiling(news, monkeypatch):
    """Asserted on the argument the connector passes. httpx's own default is five seconds,
    so a resolved request proves only that somebody's default applied."""
    passed: dict = {}

    def spy(url, **kwargs):
        passed.update(kwargs)
        return httpx.Response(200, text=recorded('bbc-news.xml'), request=httpx.Request('GET', url))

    monkeypatch.setattr(httpx, 'get', spy)
    connector(news()).candidates(50)

    assert passed['timeout'] == 10.0, 'the connector did not choose a ceiling of its own'


def test_the_article_call_carries_a_fifteen_second_ceiling(news, monkeypatch):
    """An article page gets longer than a feed — half a megabyte of news-site HTML against
    a 60 KB document. Asserted on the argument, because httpx has a default of its own and
    a call that chose nothing looks identical from outside."""
    asked: list[dict] = []

    def spy(url, **kwargs):
        asked.append({'url': str(url), **kwargs})
        article = 'bbc.co.uk/news/articles' in str(url)
        body = recorded('bbc-article.html') if article else recorded('bbc-news.xml')
        return httpx.Response(200, text=body, request=httpx.Request('GET', url))

    monkeypatch.setattr(httpx, 'get', spy)
    reader = connector(news(settings=f'FEEDS=bbc=BBC News={BBC}\n'))
    reader.article('bbc-2026-09-14-russia-hits-ukrainian-train-shortly')

    page = next(call for call in asked if 'bbc.co.uk/news/articles' in call['url'])
    assert page['timeout'] == 15.0, 'the article fetch did not choose a ceiling of its own'
    assert page['follow_redirects'] is True, 'VRT links are short URLs that redirect'


# ---------------------------------------------------------------------------
# Fetched once every five minutes
# ---------------------------------------------------------------------------


@respx.mock
def test_a_feed_is_downloaded_once_within_five_minutes(news):
    """One morning page is a search and a handful of article reads, each of which
    re-resolves its id. Without this it is seven downloads of the same two documents."""
    both_feeds()
    reader = connector(news())

    for _ in range(4):
        reader.candidates(50)

    assert respx.get(VRT).call_count == 1
    assert respx.get(BBC).call_count == 1


@respx.mock
def test_a_feed_fetched_six_minutes_ago_is_fetched_again(news):
    both_feeds()
    reader = connector(news())
    clock = datetime(2026, 9, 14, 7, 0, tzinfo=timezone.utc)
    reader._now = lambda: clock  # noqa: SLF001

    reader.candidates(50)
    clock = clock + timedelta(minutes=6)
    reader._now = lambda: clock  # noqa: SLF001
    reader.candidates(50)

    assert respx.get(VRT).call_count == 2


@respx.mock
def test_a_feed_that_failed_is_never_served_from_an_older_success(news):
    """A headline list that silently ages is worse than a short one, because nothing on the
    page says how old it is."""
    both_feeds()
    reader = connector(news())
    clock = datetime(2026, 9, 14, 7, 0, tzinfo=timezone.utc)
    reader._now = lambda: clock  # noqa: SLF001

    assert len(reader.candidates(50)) == 16

    clock = clock + timedelta(minutes=6)
    reader._now = lambda: clock  # noqa: SLF001
    respx.get(VRT).mock(return_value=httpx.Response(404))
    answer = reader.search(limit=50)

    assert [c['feed'] for c in answer['candidates']] == ['bbc'] * 8, 'no VRT headlines from the last fetch'
    assert answer['unavailable'][0]['source'] == 'VRT NWS'


# ---------------------------------------------------------------------------
# The boundary
# ---------------------------------------------------------------------------


def test_the_connector_imports_the_sdk_and_nothing_else():
    from harry.boundary import forbidden_imports

    assert forbidden_imports(REPO / '.harry' / 'connectors' / 'news') == []
    assert forbidden_imports(REPO / '.harry' / 'tools' / 'news_search') == []
    assert forbidden_imports(REPO / '.harry' / 'tools' / 'news_article') == []


# ---------------------------------------------------------------------------
# The feeds themselves, which no fixture can vouch for
# ---------------------------------------------------------------------------


@pytest.mark.live
def test_the_real_feeds_still_serve_what_was_recorded():
    """The one thing the fixtures cannot prove: that VRT NWS and the BBC still answer.

    Everything above asserts what Harry does with two documents recorded on 14 September
    2026. This reaches both URLs for real, so it fails the day a feed moves, changes format
    or starts refusing scripted clients — which is exactly the failure the fixtures make
    invisible.

    Run it deliberately: `make test-live ARGS=tests/test_news_connector.py`.
    """
    found = load().get('connector', 'news')
    assert found is not None and found.target is not None, 'no news connector on disk'

    answer = found.target.search(limit=50, detail='full')

    assert answer['unavailable'] == [], 'a configured feed did not answer'
    assert len(answer['candidates']) >= 20, 'both feeds should be carrying stories'
    assert {candidate['feed'] for candidate in answer['candidates']} == {'vrt', 'bbc'}
    for candidate in answer['candidates']:
        assert candidate['title'] and candidate['link'] and candidate['published'], candidate


@pytest.mark.live
def test_a_real_article_still_extracts():
    """A news site that starts blocking scripted clients does it without announcing it.

    Takes the newest BBC story, because the BBC is the one whose page shape this was built
    against and the one with a redirect-free link.
    """
    found = load().get('connector', 'news')
    assert found is not None and found.target is not None

    newest = next(c for c in found.target.candidates(50) if c['feed'] == 'bbc')
    article = found.target.article(newest['id'])

    assert article['available'] is True, article.get('why')
    assert len(article['text']) > 500, article['text'][:200]


# ---------------------------------------------------------------------------
# A feed that answers, and carries nothing
# ---------------------------------------------------------------------------


@respx.mock
def test_a_feed_that_answers_empty_is_reported(news):
    """VRT served this exact document at 19:00 on 14 September 2026 — 555 bytes of header and
    no entries, three fetches running, an hour after carrying fifty stories.

    It is not unreadable, so it does not raise. It is also not a quiet hour: a shorter
    candidate list is indistinguishable from a slow news day in Belgium, which is the failure
    this whole connector is arranged against.
    """
    serving(**{VRT: 'vrt-empty.xml', BBC: 'bbc-news.xml'})
    built = news()

    answer = connector(built).search(limit=50)

    assert len(answer['candidates']) == 8, 'the BBC should be untouched by it'
    assert answer['unavailable'] == [{'source': 'VRT NWS', 'why': 'VRT NWS answered an empty feed'}]
    _, sink = built
    assert sink.heard == ['VRT NWS: it answered an empty feed']


@respx.mock
def test_an_empty_feed_is_keyed_apart_from_a_dead_one(news):
    """A feed that 404s in the morning must not silence the same feed answering empty in the
    afternoon. They are different faults with different fixes."""
    serving(**{BBC: 'bbc-news.xml'})
    respx.get(VRT).mock(return_value=httpx.Response(404))
    built = news()
    reader = connector(built)

    reader.search(limit=50)
    reader._cached.clear()  # noqa: SLF001 — otherwise the second read never reaches the feed
    serving(**{VRT: 'vrt-empty.xml'})
    reader.search(limit=50)

    _, sink = built
    assert len(sink.heard) == 2, sink.heard
    assert any('answered 404' in line for line in sink.heard)
    assert any('empty feed' in line for line in sink.heard)


@respx.mock
def test_a_feed_carrying_stories_reports_nothing(news):
    """The control has to be able to stay quiet, or it will be muted within a week."""
    both_feeds()
    built = news()

    assert connector(built).search(limit=50)['unavailable'] == []
    _, sink = built
    assert sink.heard == []


@respx.mock
def test_every_feed_empty_is_still_a_list_rather_than_an_error(news):
    """The morning page has to render. An empty news section is a section."""
    serving(**{VRT: 'vrt-empty.xml', BBC: 'vrt-empty.xml'})
    built = news()

    answer = connector(built).search(limit=50)

    assert answer['candidates'] == []
    assert [row['source'] for row in answer['unavailable']] == ['VRT NWS', 'BBC News']
    _, sink = built
    assert len(sink.heard) == 2


# ---------------------------------------------------------------------------
# The picture the feed published, and the summary it wrote
# ---------------------------------------------------------------------------


@respx.mock
def test_a_vrt_candidate_carries_the_picture_from_its_enclosure(news):
    """VRT attaches a picture as an Atom link with `rel="enclosure"`. It was being parsed
    and thrown away, so a page of headlines had no pictures on it."""
    both_feeds()

    found = connector(news()).candidates(50)

    vrt = [candidate for candidate in found if candidate['feed'] == 'vrt']
    assert vrt[0]['image'].startswith('https://images.vrt.be/vrtnws_share/')
    assert all(candidate['image'] for candidate in vrt), 'every VRT entry in the fixture has one'


@respx.mock
def test_a_bbc_candidate_asks_for_a_picture_rather_than_a_postage_stamp(news):
    """The feed publishes 240px and the same path serves any size. 240 is a thumbnail on a
    page read at arm's length."""
    assert '/standard/240/' in recorded('bbc-news.xml'), 'the feed still publishes the small one'
    both_feeds()

    found = connector(news()).candidates(50)

    bbc = [candidate for candidate in found if candidate['feed'] == 'bbc']
    assert bbc[0]['image'].startswith('https://ichef.bbci.co.uk/ace/standard/800/')
    assert not any('/standard/240/' in (candidate['image'] or '') for candidate in bbc)


@respx.mock
def test_nothing_is_fetched_to_find_out_what_a_picture_is(news):
    """The connector hands over the address. Forty candidates carry about thirty pictures,
    and fetching them all to list headlines is 3.6 MB for pictures mostly about to be
    discarded — so the only requests here are the two feeds."""
    both_feeds()

    connector(news()).candidates(50)

    assert len(respx.calls) == 2, 'two feeds, two requests, no pictures'


@respx.mock
def test_a_feed_with_no_pictures_is_a_feed_not_a_fault(news, caplog):
    """`collision.xml` is three real-shaped entries with no image on any of them. A source
    that simply does not publish pictures must not look like a source that broke."""
    assert 'enclosure' not in recorded('collision.xml')
    serving(**{VRT: 'collision.xml', BBC: 'bbc-news.xml'})
    built = news()

    with caplog.at_level(logging.WARNING, logger='harry.capability.news'):
        found = connector(built).candidates(50)

    assert [candidate['image'] for candidate in found if candidate['feed'] == 'vrt'] == [None, None, None]
    assert built[1].heard == [], 'nothing for Slack'


@respx.mock
def test_an_article_carries_the_summary_the_feed_wrote(news):
    """`article()` rebuilt its answer from five keys and dropped the one thing that was
    always going to be readable."""
    both_feeds()
    client = connector(news())
    story = next(c for c in client.candidates(50) if c['feed'] == 'vrt')
    respx.get(story['link']).mock(return_value=httpx.Response(200, text=recorded('vrt-article.html')))

    got = client.article(story['id'])

    assert got['summary'] == story['summary']
    assert got['image'] == story['image']
    assert got['available'] is True


@respx.mock
def test_a_story_whose_page_will_not_load_still_has_something_to_print(news):
    """The degraded path, and the reason `summary` is on the article at all: a page that
    answers 403 leaves the feed's own description as the whole of the story."""
    both_feeds()
    client = connector(news())
    story = next(c for c in client.candidates(50) if c['feed'] == 'vrt')
    respx.get(story['link']).mock(return_value=httpx.Response(403))

    got = client.article(story['id'])

    assert got['available'] is False and got['why']
    assert got['summary'] == story['summary'] and got['summary'] != ''
    assert got['image'] == story['image']
