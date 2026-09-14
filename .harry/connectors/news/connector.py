"""Two news feeds, read into one list of candidates, plus the full text of a chosen story.

Nothing here ranks, filters by importance or summarises. It fetches, parses, deduplicates
and hands over what the feeds carried — choosing among forty headlines is the judgement the
whole design keeps on Claude's side.

## Two formats, on purpose

The BBC serves RSS 2.0 and VRT NWS serves Atom, so `_parse` has a branch for each and maps
both onto one candidate shape. A parser written for RSS alone reads the VRT document
without error and returns nothing, because "no items" and "I do not understand this" look
the same from outside. The alternative was `feedparser`, which was rejected for how it
fails: it flags a document it cannot read rather than raising, so the unavailable-source
path would rest on remembering to check a field.

## What a failure costs

One source. A feed that 404s, times out, answers HTML or answers a document declaring a
DOCTYPE is listed in `unavailable` with a reason, the other feeds still return, and one
line goes to Slack. That last part is not decoration: a dead news feed is invisible on the
page — the list is just shorter — where a dead weather source leaves "Weather unavailable"
in the place the forecast should be.
"""

from __future__ import annotations

import logging
import re
import unicodedata
import xml.etree.ElementTree as ElementTree
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit, urlunsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
import trafilatura

from harry.sdk import Context, Registry

ATOM = 'http://www.w3.org/2005/Atom'

FEED_TIMEOUT = 10.0
"""Seconds. Longer than the weather's five: these are 20–60 KB documents from a CDN, and
the morning page can wait ten seconds for the thing it is mostly made of."""

ARTICLE_TIMEOUT = 15.0
"""Seconds. A full article page is half a megabyte of news-site HTML."""

FRESH_FOR = timedelta(minutes=5)
"""How long a fetched feed is reused. One digest is one `news_search` and then a handful of
`news_article` calls, each of which re-resolves its id against the feeds — without this,
building a page would download the same two documents seven times.

**Only a success is cached.** A feed that failed is retried on the next call, and a feed
that is down is never served from an older success: a headline list that silently ages is
worse than a short one, because nothing on the page says how old it is.
"""

DEFAULT_LIMIT = 20
MAX_LIMIT = 50
"""Forty candidates is what the morning page is chosen from, so fifty is the ceiling and
twenty is what you get without asking."""

ID_WORDS = 5
"""Words of the title in an id. Five fits `vrt-2026-09-14-tessenderlo-ham-hakt-knoop-door`
on one line and still reads as the story it points at."""

USER_AGENT = (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36'
)
"""Article pages are served to browsers. Asking as one is what gets the article rather than
a consent wall — and following the redirect is what turns a `vrtnws.be/p.oL1bKEomY` link
into the page the story is on."""

MINIMUM_TEXT = 200
"""Characters. Below this the extractor found a navigation bar, not an article."""

CONCISE_SUMMARY = 200
"""Characters of the feed's summary in a concise candidate, which is the default.

Twenty candidates is twenty summaries in the caller's context on every call, and a feed's
description runs to several hundred characters. Two hundred is enough to tell what a story
is about, which is all a candidate is for — the whole thing is a `detail="full"` away, and
the article itself is one `news_article` away.
"""

CONCISE_FIELDS = ('id', 'title', 'source', 'feed', 'date')
"""What survives `detail="concise"`, besides the trimmed summary. `published` and `link`
are dropped: `date` is the part a person reads, and nothing chooses a story by its URL."""


class Unreadable(Exception):
    """This document is not a feed Harry can read. One source unavailable, never fatal."""


class UnknownStory(Exception):
    """No configured feed carries that id — the caller's mistake, so it raises."""


@dataclass(frozen=True)
class Feed:
    """One configured source: what starts its ids, what a person reads, where it lives."""

    slug: str
    name: str
    url: str


def read_feeds(setting: str, log: logging.Logger) -> list[Feed]:
    """`slug=Name=url|slug=Name=url` into feeds, skipping anything malformed.

    Split on the first two `=` so a URL may carry as many more as it likes. A malformed
    entry is skipped and logged rather than raising, because one typo in a list of four
    feeds should cost one feed.
    """
    feeds: list[Feed] = []
    for entry in setting.split('|'):
        entry = entry.strip()
        if not entry:
            continue
        slug, _, rest = entry.partition('=')
        name, _, url = rest.partition('=')
        if not (slug.strip() and name.strip() and url.strip()):
            log.warning('skipping a FEEDS entry that is not slug=Name=url: %r', entry)
            continue
        feeds.append(Feed(slug=slug.strip(), name=name.strip(), url=url.strip()))
    return feeds


def _slug(text: str) -> str:
    """A title into url-safe words. Accents folded, so Tsjechië and Tsjechie are one word."""
    flattened = unicodedata.normalize('NFKD', text)
    plain = ''.join(character for character in flattened if not unicodedata.combining(character))
    return re.sub(r'-+', '-', re.sub(r'[^a-z0-9]+', '-', plain.lower())).strip('-')


def _canonical(link: str) -> str:
    """The part of a URL that says which story it is.

    Query and fragment go: the BBC's feed links carry `?at_medium=RSS`, its `<guid>` carries
    `#0`, and both point at the same article. The host is lowercased and the path is not —
    `vrtnws.be/p.oL1bKEomY` is case-sensitive and lowercasing it produces a 404.
    """
    parts = urlsplit(link.strip())
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip('/'), '', ''))


def _when(published: str | None) -> datetime | None:
    """A feed's date, in UTC. RSS 2.0 uses RFC 822 and Atom uses ISO 8601; both are here.

    A third spelling returns None, and a candidate with no date sorts last rather than
    taking the whole feed down with it.
    """
    if not published:
        return None
    text = published.strip()
    for read in (lambda: datetime.fromisoformat(text.replace('Z', '+00:00')), lambda: parsedate_to_datetime(text)):
        try:
            at = read()
        except (ValueError, TypeError):
            continue
        return at.astimezone(timezone.utc) if at.tzinfo else at.replace(tzinfo=timezone.utc)
    return None


def _refuse_entities(document: str) -> None:
    """A feed that declares its own entities is refused before any parser sees it.

    `xml.etree.ElementTree` does not fetch external entities — `<!ENTITY e SYSTEM
    "file:///etc/passwd">` raises rather than reading the disk. It does expand *internal*
    ones, so a few hundred bytes of nested declarations expand to gigabytes and take the
    machine's memory. Those declarations can only arrive one way: inside the square
    brackets of a `<!DOCTYPE`, which is what this looks for.

    A bare `<!doctype html>` is not refused. It carries no declarations, and an HTML error
    page served where a feed was expected should fail as "this is not XML" — the reason a
    person can act on.

    Only the prologue is searched, which is everything before the root element's start tag.
    A feed quoting the string inside an article description is not refused.
    """
    for index, character in enumerate(document):
        if character == '<' and document[index + 1 : index + 2] not in ('?', '!', '/'):
            document = document[:index]
            break
    at = document.upper().find('<!DOCTYPE')
    if at >= 0 and '[' in document[at:]:
        raise Unreadable('the document declares its own entities, which a feed has no reason to do')


def _parse(document: str, feed: Feed) -> list[dict]:
    """One feed document into raw candidates, whichever of the two formats it is."""
    _refuse_entities(document)
    try:
        root = ElementTree.fromstring(document)
    except ElementTree.ParseError as error:
        raise Unreadable(f'the document is not XML ({error.msg})') from error

    if root.tag == f'{{{ATOM}}}feed':
        return [_from_atom(entry, feed) for entry in root.findall(f'{{{ATOM}}}entry')]
    items = root.findall('.//item')
    if items or root.tag == 'rss':
        return [_from_rss(item, feed) for item in items]
    raise Unreadable(f'the document is XML but not a feed (its root is <{root.tag}>)')


def _from_rss(item: ElementTree.Element, feed: Feed) -> dict:
    return {
        'title': (item.findtext('title') or '').strip(),
        'summary': (item.findtext('description') or '').strip(),
        'link': (item.findtext('link') or item.findtext('guid') or '').strip(),
        'at': _when(item.findtext('pubDate')),
        'source': feed.name,
        'feed': feed.slug,
    }


def _from_atom(entry: ElementTree.Element, feed: Feed) -> dict:
    """An Atom entry, taking `rel="alternate"` as the story.

    VRT's entries carry three links. `rel="self"` looks like the obvious one and is a
    per-article `.rss.xml` document — the entry again, not the article. `rel="alternate"` is
    the short link that redirects to the page a person would read.
    """
    links = entry.findall(f'{{{ATOM}}}link')
    chosen = next((link for link in links if link.get('rel') == 'alternate'), None)
    if chosen is None:
        chosen = next((link for link in links if link.get('rel') not in ('self', 'enclosure')), None)
    return {
        'title': (entry.findtext(f'{{{ATOM}}}title') or '').strip(),
        'summary': (entry.findtext(f'{{{ATOM}}}summary') or '').strip(),
        'link': (chosen.get('href') if chosen is not None else entry.findtext(f'{{{ATOM}}}id')) or '',
        'at': _when(entry.findtext(f'{{{ATOM}}}published') or entry.findtext(f'{{{ATOM}}}updated')),
        'source': feed.name,
        'feed': feed.slug,
    }


class News:
    """Every configured feed, as one list of candidates and one way to read a story."""

    def __init__(
        self,
        feeds: Iterable[Feed],
        zone: ZoneInfo,
        alert: Callable[..., bool],
        log: logging.Logger,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._feeds = list(feeds)
        self._zone = zone
        self._alert = alert
        self._log = log
        self._now = now
        self._cached: dict[str, tuple[datetime, str]] = {}

    # -- what the digest calls ------------------------------------------------

    def candidates(self, limit: int = DEFAULT_LIMIT) -> list[dict]:
        """Today's headlines, newest first. The signature the morning page was built for.

        A plain list, and it stays one. It cannot say that a feed died, and it is not asked
        to: the page learns that from Slack, and `search` — a different caller with a
        different need — gets `unavailable` alongside its candidates. A list that sometimes
        returned a dict would be two shapes nobody could rely on.
        """
        return self.search(limit=limit, detail='full')['candidates']

    def article(self, story_id: str) -> dict:
        """The full text of one candidate, resolved by id against the feeds.

        Re-resolving rather than reading something `search` left behind is what lets the
        digest hold nothing between its two calls. An id no feed carries is the caller's
        mistake, so it raises; a page that will not load is not, so it answers.
        """
        found, _ = self._gather()
        story = next((candidate for candidate in found if candidate['id'] == story_id), None)
        if story is None:
            raise UnknownStory(f'no feed carries {story_id!r} — run news_search again, the feeds have moved on')

        known = {key: story[key] for key in ('id', 'title', 'source', 'published', 'link')}
        try:
            text = self._read(story['link'])
        except (httpx.HTTPError, Unreadable) as error:
            why = _why(error, story['source'], ARTICLE_TIMEOUT)
            self._log.warning('no text for %s: %s', story_id, why)
            self._alert(f'{story["source"]}: {why}', key=f'article:{story["feed"]}')
            return {**known, 'available': False, 'why': why}
        return {**known, 'available': True, 'text': text}

    # -- what the tools call --------------------------------------------------

    def search(
        self,
        query: str | None = None,
        source: str | None = None,
        since: str | None = None,
        limit: int = DEFAULT_LIMIT,
        detail: str = 'concise',
    ) -> dict:
        """Candidates narrowed, capped, trimmed, and whatever could not be reached.

        `unavailable` rides along with the answer so a dead feed is visible to Claude as
        well as in Slack — a shorter list on its own says nothing.
        """
        found, unavailable = self._gather()
        if source:
            found = [candidate for candidate in found if candidate['feed'] == source]
        if since:
            found = [candidate for candidate in found if candidate['date'] >= since]
        if query:
            wanted = query.lower()
            found = [
                candidate
                for candidate in found
                if wanted in candidate['title'].lower() or wanted in candidate['summary'].lower()
            ]
        kept = found[: max(1, min(limit, MAX_LIMIT))]
        if detail != 'full':
            kept = [_concise(candidate) for candidate in kept]
        return {'candidates': kept, 'unavailable': unavailable}

    # -- the work -------------------------------------------------------------

    def _gather(self) -> tuple[list[dict], list[dict]]:
        """Every feed, deduplicated, newest first, with the failures listed separately.

        Feeds are walked in configured order and the first one carrying a story keeps it,
        so which copy of a duplicate you get is a decision somebody made in `FEEDS` rather
        than a race between two downloads.
        """
        by_link: dict[str, dict] = {}
        taken: set[str] = set()
        unavailable: list[dict] = []

        for feed in self._feeds:
            try:
                raw = _parse(self._fetch(feed), feed)
            except (httpx.HTTPError, Unreadable) as error:
                why = _why(error, feed.name, FEED_TIMEOUT)
                self._log.warning('%s is unavailable: %s', feed.name, why)
                self._alert(f'{feed.name}: {why}', key=f'feed:{feed.slug}')
                unavailable.append({'source': feed.name, 'why': why})
                continue
            for item in raw:
                key = _canonical(item['link'])
                if not key or key in by_link:
                    continue
                by_link[key] = self._as_candidate(item, taken)

        newest_first = sorted(by_link.values(), key=lambda candidate: candidate['published'] or '', reverse=True)
        return newest_first, unavailable

    def _as_candidate(self, item: dict, taken: set[str]) -> dict:
        """A parsed item with the id and the local date it is filed under."""
        at = item['at']
        local = at.astimezone(self._zone) if at else self._now().astimezone(self._zone)
        date = local.strftime('%Y-%m-%d')
        story_id = self._unique(f'{item["feed"]}-{date}-{"-".join(_slug(item["title"]).split("-")[:ID_WORDS])}', taken)
        return {
            'id': story_id,
            'title': item['title'],
            'source': item['source'],
            'feed': item['feed'],
            'published': at.isoformat() if at else None,
            'date': date,
            'summary': item['summary'],
            'link': item['link'],
        }

    @staticmethod
    def _unique(story_id: str, taken: set[str]) -> str:
        """Two stories on one day whose first words match still get one id each."""
        candidate, suffix = story_id, 1
        while candidate in taken:
            suffix += 1
            candidate = f'{story_id}-{suffix}'
        taken.add(candidate)
        return candidate

    def _fetch(self, feed: Feed) -> str:
        """One feed document, at most once every `FRESH_FOR`."""
        cached = self._cached.get(feed.url)
        if cached and self._now() - cached[0] < FRESH_FOR:
            self._log.debug('%s is still fresh', feed.name)
            return cached[1]
        response = httpx.get(feed.url, timeout=FEED_TIMEOUT, follow_redirects=True)
        response.raise_for_status()
        self._cached[feed.url] = (self._now(), response.text)
        return response.text

    def _read(self, link: str) -> str:
        """One article page, as the prose a person would read."""
        response = httpx.get(
            link,
            timeout=ARTICLE_TIMEOUT,
            follow_redirects=True,
            headers={'User-Agent': USER_AGENT},
        )
        response.raise_for_status()
        text = trafilatura.extract(response.text, url=str(response.url), favor_precision=True) or ''
        if len(text.strip()) < MINIMUM_TEXT:
            raise Unreadable('the page loaded but there was no article text in it')
        return text.strip()


def _concise(candidate: dict) -> dict:
    """The same candidate, at about a third of the characters."""
    summary = candidate['summary']
    if len(summary) > CONCISE_SUMMARY:
        summary = summary[:CONCISE_SUMMARY].rstrip() + '…'
    return {**{field: candidate[field] for field in CONCISE_FIELDS}, 'summary': summary}


def _why(error: Exception, name: str, ceiling: float) -> str:
    """What to tell somebody, from what went wrong. One sentence, no traceback, no URL.

    The URL stays out deliberately: this sentence goes to Slack, and a feed URL can carry a
    key in its query string.

    `ceiling` is passed rather than read from a constant because the two callers wait for
    different lengths of time, and the number in a line somebody reads over coffee is the
    part they would act on.
    """
    if isinstance(error, Unreadable):
        return str(error)
    if isinstance(error, httpx.TimeoutException):
        return f'{name} did not answer within {ceiling:g}s'
    if isinstance(error, httpx.HTTPStatusError):
        return f'{name} answered {error.response.status_code}'
    return f'{name} could not be reached'


def register(registry: Registry, context: Context) -> None:
    feeds = read_feeds(str(context.config['feeds']), context.log)
    if not feeds:
        raise ValueError('FEEDS is empty — a news connector with no feeds has nothing to read')
    wanted = str(context.config['timezone'])
    try:
        zone = ZoneInfo(wanted)
    except (ZoneInfoNotFoundError, ValueError):
        context.log.warning('no zone called %r; filing stories under UTC instead', wanted)
        zone = ZoneInfo('UTC')
    registry.connector(News(feeds, zone, context.alert, context.log))
