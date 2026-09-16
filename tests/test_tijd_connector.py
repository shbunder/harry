"""De Tijd's articles, read through a logged-in browser, and what Harry says when it cannot.

The real `.harry/connectors/tijd/` and `.harry/connectors/news/` are copied into a root and
loaded, so the declarations, the settings and the connector naming a connector are under test
together. The browser is the one thing replaced: `Script` below stands in for Chromium and plays
back pages recorded on 16 September 2026 from `tests/fixtures/tijd/`. What Chromium itself does
against the real site is `live`, at the bottom.

**No test here reaches tijd.be** except those marked `live`.
"""

from __future__ import annotations

import json
import logging
import shutil
import stat
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from fastmcp import Client

from harry.alerts import Alerts
from harry.loader import load
from harry.mcp import FIND_TOOLS, build_server
from harry.registry import LOADED
from harry.store import Store

from .capability_copy import copy_capability

REPO = Path(__file__).parent.parent
PAGES = Path(__file__).parent / 'fixtures' / 'tijd'
FEEDS = Path(__file__).parent / 'fixtures' / 'news'

TIJD_FEED = 'https://www.tijd.be/rss/nieuws.xml'
BBC_FEED = 'https://feeds.bbci.co.uk/news/rss.xml'
TRAIN = 'https://www.bbc.co.uk/news/articles/cy5zg41dkqwo'
TRAIN_ID = 'bbc-2026-09-14-russia-hits-ukrainian-train-shortly'

STUB = 'https://www.tijd.be/r/t/1/id/10686286'
"""The first item in `tijd-nieuws.xml`, and the article recorded behind it."""
STORY = 'tijd-2026-09-16-makke-von-der-leyen-steekt'
ARTICLE = (
    'https://www.tijd.be/politiek-economie/europa/algemeen/'
    'makke-von-der-leyen-steekt-hand-uit-naar-canada-maar-biedt-geen-inspiratie-aan-europa/10686286.html'
)

EMAIL = 'reader@example.com'
PASSWORD = 'correct-horse-battery-staple'
HOME = 'https://www.tijd.be/'
PASSWORD_STEP = 'https://auth.mediafin.be/u/login/password'

NOW = datetime(2026, 9, 16, 6, 30, tzinfo=timezone.utc)


def page(name: str) -> str:
    return (PAGES / name).read_text(encoding='utf-8')


@dataclass(frozen=True)
class Visit:
    status: int | None
    url: str
    html: str


@dataclass(frozen=True)
class End:
    step: str
    url: str
    html: str


LOGGED_IN = Visit(200, ARTICLE, page('article-logged-in.html'))
LOGGED_OUT = Visit(200, ARTICLE, page('article-logged-out.html'))
BACK_HOME = End('password', HOME, '<html lang="nl"></html>')
REFUSED = End('password', PASSWORD_STEP, page('login-refused.html'))


class Script:
    """What the stand-in browser does, and what was asked of it.

    `pages` and `logins` are played in order; the last entry repeats. An entry that is an
    exception class is raised, with the password in its message — the one place a careless
    rule would copy it from.
    """

    def __init__(self) -> None:
        self.pages: list[Any] = [LOGGED_IN]
        self.logins: list[Any] = [BACK_HOME]
        self.on_start: type[Exception] | None = None
        self.opened_with: list[Path | None] = []
        self.visited: list[str] = []
        self.logged_in: list[tuple[str, str, float]] = []
        self.state = {'cookies': [{'name': 'session', 'value': 'renewed'}], 'origins': []}
        self.pause = 0.0
        self.busy = 0
        self.most_at_once = 0
        self.page_budgets: list[float] = []

    def __call__(self, state: Path | None) -> Script:
        self.opened_with.append(state)
        return self

    def __enter__(self) -> Script:
        if self.on_start is not None:
            raise self.on_start(f'the browser would not start ({PASSWORD})')
        return self

    def __exit__(self, *_: object) -> None:
        return None

    @staticmethod
    def _next(queue: list[Any]) -> Any:
        return queue.pop(0) if len(queue) > 1 else queue[0]

    def _play(self, entry: Any) -> Any:
        if isinstance(entry, type) and issubclass(entry, Exception):
            raise entry(f'net::ERR_SOMETHING {PASSWORD} {EMAIL}')
        return entry

    def visit(self, link: str, seconds: float) -> Any:
        self.page_budgets.append(seconds)
        self.busy += 1
        self.most_at_once = max(self.most_at_once, self.busy)
        try:
            time.sleep(self.pause)
            self.visited.append(link)
            return self._play(self._next(self.pages))
        finally:
            self.busy -= 1

    def log_in(self, email: str, password: str, seconds: float) -> Any:
        self.logged_in.append((email, password, seconds))
        return self._play(self._next(self.logins))

    def storage_state(self) -> dict:
        return self.state


class Clock:
    def __init__(self) -> None:
        self.now = NOW

    def __call__(self) -> datetime:
        return self.now


class Somewhere:
    def __init__(self) -> None:
        self.heard: list[str] = []

    def __call__(self, message: str) -> None:
        self.heard.append(message)


@dataclass
class Harry:
    root: Path
    catalogue: Any
    sink: Somewhere
    script: Script
    clock: Clock
    session: Path

    @property
    def tijd(self) -> Any:
        found = self.catalogue.get('connector', 'tijd')
        assert found is not None and found.status == LOADED, found and found.reason
        return found.target

    @property
    def news(self) -> Any:
        return self.catalogue.get('connector', 'news').target

    def failures(self) -> Any:
        """The exception classes the connector itself catches, as it imported them."""
        return sys.modules[type(self.tijd).__module__]


@pytest.fixture
def harry(tmp_path, monkeypatch):
    """news, tijd and news_article from the real tree, with De Tijd's feed configured."""
    for prefix in ('HARRY_NEWS_', 'HARRY_TIJD_'):
        for key in [key for key in list(__import__('os').environ) if key.startswith(prefix)]:
            monkeypatch.delenv(key, raising=False)
    monkeypatch.delenv('HARRY_CAPABILITY_SETTINGS_DIR', raising=False)

    def build(*, with_tijd: bool = True, feeds: str = f'tijd=De Tijd={TIJD_FEED}|bbc=BBC News={BBC_FEED}') -> Harry:
        root = tmp_path / 'root'
        wanted = ['connectors/news', 'tools/news_article', *(['connectors/tijd'] if with_tijd else [])]
        for where in wanted:
            (root / where).parent.mkdir(parents=True, exist_ok=True)
            copy_capability(REPO / '.harry' / where, root / where)
        (root / 'connectors' / 'news' / '.env.local').write_text(f'FEEDS={feeds}\n', encoding='utf-8')
        session = tmp_path / 'data' / 'tijd'
        if with_tijd:
            (root / 'connectors' / 'tijd' / '.env.local').write_text(
                f'EMAIL={EMAIL}\nPASSWORD={PASSWORD}\nSESSION_DIR={session}\n', encoding='utf-8'
            )
        alerts = Alerts()
        catalogue = load([root], alerts=alerts)
        alerts.attach(catalogue)
        sink = Somewhere()
        alerts._sinks = [sink]  # noqa: SLF001 — no Slack connector in this root to take them
        script, clock = Script(), Clock()
        built = Harry(root, catalogue, sink, script, clock, session)
        if with_tijd:
            built.tijd._browser = script  # noqa: SLF001 — the one thing replaced: Chromium
            built.tijd._now = clock  # noqa: SLF001
        return built

    return build


def feeds_are_up() -> None:
    respx.get(TIJD_FEED).mock(return_value=httpx.Response(200, text=(FEEDS / 'tijd-nieuws.xml').read_text()))
    respx.get(BBC_FEED).mock(return_value=httpx.Response(200, text=(FEEDS / 'bbc-news.xml').read_text()))


async def article(built: Harry, story: str = STORY) -> dict:
    """`news_article`, the way a session reaches it."""
    server = build_server(built.catalogue, Store(built.root.parent / 'jobs.json'))
    async with Client(server) as connected:
        await connected.call_tool(FIND_TOOLS, {'query': 'news'})
        result = await connected.call_tool('news_article', {'id': story}, raise_on_error=False)
    assert result.is_error is False, result.content
    return result.data


# ---------------------------------------------------------------------------
# The rules, against recorded pages
# ---------------------------------------------------------------------------


def pages_module(built: Harry) -> Any:
    return sys.modules[type(built.tijd).__module__ + '.pages']


def test_the_logged_out_page_is_paywalled_and_the_logged_in_one_is_not(harry):
    rules = pages_module(harry())
    assert rules.paywalled(LOGGED_OUT.html) is True
    assert rules.paywalled(LOGGED_IN.html) is False


def test_a_login_that_came_back_to_tijd_be_finished(harry):
    assert pages_module(harry()).login_outcome(BACK_HOME) is None


def test_the_recorded_refusal_is_a_refusal_though_its_script_talks_about_captchas(harry):
    """The real page mentions "captcha" 77 times with none shown. A rule matching the word
    would send the owner hunting for a captcha when the password is simply wrong."""
    assert 'data-captcha-provider' in REFUSED.html
    assert pages_module(harry()).login_outcome(REFUSED) == 'refused'


def test_a_captcha_element_is_a_challenge(harry):
    captcha = End('password', PASSWORD_STEP, page('login-captcha.html'))
    assert pages_module(harry()).login_outcome(captcha) == 'challenge'


def test_a_page_that_neither_finished_nor_refused_is_a_login_page_harry_does_not_know(harry):
    """Including one whose script mentions captchas — a word is not an element."""
    unexpected = End('password', PASSWORD_STEP, page('login-unexpected.html'))
    assert 'data-captcha-provider' in unexpected.html
    assert pages_module(harry()).login_outcome(unexpected) == 'login-page'


def test_finishing_the_email_step_on_tijd_be_is_not_finishing_the_login(harry):
    """Only the password step ends a login."""
    assert pages_module(harry()).login_outcome(End('email', HOME, '<html></html>')) == 'login-page'


def test_the_login_hand_over_page_is_not_the_end_of_the_login(harry):
    """Measured: the password step lands on `login-redirect.html`, which navigates on a second
    and a half later. Stopping there sent the next page load into the middle of that redirect."""
    landed = pages_module(harry()).LANDED
    assert landed.search('https://www.tijd.be/')
    assert landed.search(ARTICLE)
    assert not landed.search('https://www.tijd.be/login-redirect.html')
    assert not landed.search(PASSWORD_STEP)


class Interrupted:
    """A page whose first load is abandoned by a redirect still finishing, as Chromium reports it."""

    def __init__(self, error: type[Exception], messages: list[str]) -> None:
        self.error, self.messages, self.url, self.loads = error, messages, ARTICLE, 0

    def goto(self, link: str, **_: Any) -> Any:
        self.loads += 1
        if self.messages:
            raise self.error(self.messages.pop(0))
        return type('Response', (), {'status': 200})()

    def content(self) -> str:
        return LOGGED_IN.html


def chromium_with(built: Harry, *messages: str) -> tuple[Any, Interrupted]:
    from playwright.sync_api import Error

    module = sys.modules[type(built.tijd).__module__ + '.browser']
    browser = module.Chromium(None)
    page = Interrupted(Error, list(messages))
    browser._page = page  # noqa: SLF001 — the page Chromium would drive
    return browser, page


def test_a_load_the_page_s_own_redirect_abandoned_is_tried_once_more(harry):
    built = harry()
    browser, page = chromium_with(built, 'Page.goto: net::ERR_ABORTED at https://www.tijd.be/r/t/1/id/10686286')

    visit = browser.visit(STUB, 30)

    assert visit.status == 200
    assert page.loads == 2


def test_a_second_abandoned_load_is_not_a_race_and_says_the_page_did_not_load(harry):
    built = harry()
    browser, page = chromium_with(built, 'net::ERR_ABORTED', 'net::ERR_ABORTED')

    with pytest.raises(built.failures().PageDidNotLoad):
        browser.visit(STUB, 30)
    assert page.loads == 2


def test_a_network_failure_is_the_page_s_and_anything_else_is_the_browser_s(harry):
    built = harry()
    browser, page = chromium_with(built, 'net::ERR_NAME_NOT_RESOLVED')
    with pytest.raises(built.failures().PageDidNotLoad):
        browser.visit(STUB, 30)
    assert page.loads == 1, 'only an abandoned load is tried again'

    browser, _ = chromium_with(built, 'Target page, context or browser has been closed')
    with pytest.raises(built.failures().BrowserFailed):
        browser.visit(STUB, 30)


# ---------------------------------------------------------------------------
# De Tijd's links go to the tijd connector, and nothing else does
# ---------------------------------------------------------------------------


@respx.mock
async def test_de_tijd_s_feed_is_read_like_any_other(harry):
    feeds_are_up()
    built = harry()

    found = built.news.search(source='tijd', limit=50, detail='full')

    assert len(found['candidates']) == 10
    assert found['candidates'][0]['id'] == STORY
    assert all(candidate['image'] is None for candidate in found['candidates']), 'the feed carries no pictures'


@respx.mock
async def test_a_de_tijd_story_comes_back_in_full_with_no_login(harry):
    feeds_are_up()
    built = harry()

    answer = await article(built)

    assert answer['available'] is True
    assert len(answer['text']) > 1000
    assert built.script.visited == [STUB], 'the redirect stub goes to the browser as the feed gave it'
    assert built.script.logged_in == []
    assert built.sink.heard == []


@respx.mock
async def test_the_session_is_written_back_whole_and_readable_only_by_its_owner(harry):
    feeds_are_up()
    built = harry()

    await article(built)

    saved = built.session / 'storage-state.json'
    assert json.loads(saved.read_text()) == built.script.state
    assert stat.S_IMODE(saved.stat().st_mode) == 0o600
    assert [p.name for p in built.session.iterdir() if p.name.endswith('.tmp')] == [], (
        'a temporary file was left behind'
    )

    await article(built)
    assert built.script.opened_with[-1] == saved, 'the next read starts from the saved session'


@respx.mock
async def test_other_sources_never_reach_the_browser(harry):
    feeds_are_up()
    respx.get(url__startswith=TRAIN).mock(
        return_value=httpx.Response(200, text=(FEEDS / 'bbc-article.html').read_text())
    )
    built = harry()

    answer = await article(built, TRAIN_ID)

    assert answer['available'] is True
    assert built.script.visited == []


@respx.mock
async def test_without_the_tijd_connector_a_de_tijd_link_is_fetched_like_any_other(harry):
    feeds_are_up()
    respx.get(STUB).mock(return_value=httpx.Response(403, text='<html>403 Blocked</html>'))
    built = harry(with_tijd=False)

    answer = await article(built)

    assert answer['available'] is False
    assert answer['why'] == 'De Tijd answered 403'
    assert answer['summary'].startswith('Ursula von der Leyen'), 'the feed summary still prints'


# ---------------------------------------------------------------------------
# What the browser brings back, and what reaches Slack
# ---------------------------------------------------------------------------


@respx.mock
async def test_a_403_is_the_browser_being_refused_and_never_leads_to_a_login(harry):
    feeds_are_up()
    built = harry()
    built.script.pages = [Visit(403, ARTICLE, '<html><title>403 Blocked</title></html>')]

    answer = await article(built)

    assert answer['available'] is False
    assert 'refused the browser (403)' in answer['why']
    assert 'logging in again will not help' in answer['why']
    assert answer['summary'].startswith('Ursula von der Leyen')
    assert built.script.logged_in == []
    assert built.sink.heard == [f'De Tijd: {answer["why"]}'], 'one line, from tijd, and not a second from news'


@respx.mock
async def test_a_page_that_does_not_load_says_so(harry):
    feeds_are_up()
    built = harry()
    built.script.pages = [built.failures().PageDidNotLoad]

    answer = await article(built)

    assert answer['why'] == 'the article page did not load within 30 seconds, or could not be reached'


@respx.mock
async def test_a_browser_that_cannot_start_costs_de_tijd_and_nothing_else(harry):
    feeds_are_up()
    respx.get(url__startswith=TRAIN).mock(
        return_value=httpx.Response(200, text=(FEEDS / 'bbc-article.html').read_text())
    )
    built = harry()
    built.script.on_start = built.failures().BrowserFailed

    tijd = await article(built)
    bbc = await article(built, TRAIN_ID)

    assert tijd['available'] is False
    assert tijd['why'] == 'the browser Harry reads De Tijd with could not start, or stopped'
    assert bbc['available'] is True, 'the BBC story is read in the same Harry'
    assert built.sink.heard == [f'De Tijd: {tijd["why"]}']


@respx.mock
async def test_the_same_reason_twice_is_one_line_and_a_different_reason_is_a_second(harry):
    feeds_are_up()
    built = harry()
    blocked = Visit(403, ARTICLE, '<html></html>')
    built.script.pages = [blocked, blocked, built.failures().PageDidNotLoad]

    for _ in range(3):
        await article(built)

    assert len(built.sink.heard) == 2, built.sink.heard
    assert 'refused the browser' in built.sink.heard[0]
    assert 'did not load' in built.sink.heard[1]


@respx.mock
async def test_nothing_harry_says_carries_the_email_or_the_password(harry):
    """Every failure the stand-in raises carries both in its message."""
    feeds_are_up()
    built = harry()
    failures = built.failures()
    said: list[str] = []
    for playing in (failures.BrowserFailed, failures.PageDidNotLoad, failures.Refused):
        built.script.pages = [playing]
        said.append((await article(built))['why'])
    built.script.pages = [LOGGED_OUT]
    built.script.logins = [REFUSED]
    said.append((await article(built))['why'])

    for text in [*said, *built.sink.heard]:
        assert PASSWORD not in text and EMAIL not in text, text
        assert 'net::ERR' not in text, f"an exception's own text reached a person: {text}"


@respx.mock
async def test_a_page_de_tijd_answers_with_an_error_says_which(harry):
    feeds_are_up()
    built = harry()
    built.script.pages = [Visit(404, ARTICLE, '<html></html>')]

    answer = await article(built)

    assert answer['why'] == 'De Tijd answered 404 for the article'
    assert built.script.logged_in == []


@respx.mock
async def test_a_reader_that_raises_costs_that_article_and_news_says_so(harry):
    feeds_are_up()
    built = harry()
    built.script.pages = [RuntimeError]

    answer = await article(built)

    assert answer['available'] is False
    assert answer['why'] == 'the connector that reads De Tijd failed (RuntimeError)'
    assert built.sink.heard == [f'De Tijd: {answer["why"]}']


# ---------------------------------------------------------------------------
# The session on disk
# ---------------------------------------------------------------------------


@respx.mock
async def test_a_saved_session_that_is_not_a_session_is_set_aside(harry, caplog):
    feeds_are_up()
    built = harry()
    built.session.mkdir(parents=True)
    (built.session / 'storage-state.json').write_text('{"cookies": [', encoding='utf-8')

    with caplog.at_level(logging.WARNING):
        answer = await article(built)

    assert answer['available'] is True
    assert built.script.opened_with == [None], 'a broken file is never handed to the browser'
    assert any('could not be read' in record.getMessage() for record in caplog.records)


@respx.mock
async def test_a_session_that_cannot_be_written_still_returns_the_article_and_says_so(harry):
    feeds_are_up()
    built = harry()
    built.session.parent.mkdir(parents=True)
    built.session.write_text('a file where the directory should be', encoding='utf-8')

    answer = await article(built)

    assert answer['available'] is True
    assert built.sink.heard == [
        f'De Tijd: Harry could not save the De Tijd session in {built.session}, so every article will need a login until it can'
    ]


def test_two_reads_at_once_use_the_browser_one_after_the_other(harry):
    built = harry()
    built.script.pause = 0.05
    threads = [threading.Thread(target=built.tijd.read, args=(STUB,)) for _ in range(3)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(built.script.visited) == 3
    assert built.script.most_at_once == 1


# ---------------------------------------------------------------------------
# Logging in
# ---------------------------------------------------------------------------


@respx.mock
async def test_a_paywalled_page_logs_in_once_and_reads_the_article_again(harry):
    feeds_are_up()
    built = harry()
    built.script.pages = [LOGGED_OUT, LOGGED_IN]

    answer = await article(built)

    assert answer['available'] is True
    assert len(answer['text']) > 1000, 'the 263-character lead was never handed over as the story'
    assert built.script.logged_in == [(EMAIL, PASSWORD, 60.0)]
    assert built.script.visited == [STUB, STUB]
    assert built.script.page_budgets == [30.0, 30.0], (
        'two pages of 30 seconds and a 60-second login: two minutes at most'
    )
    assert (built.session / 'logged-in-at').read_text() == NOW.isoformat()
    assert built.sink.heard == []


@respx.mock
async def test_a_login_says_how_long_the_session_it_replaced_lasted(harry, caplog):
    feeds_are_up()
    built = harry()
    built.session.mkdir(parents=True)
    (built.session / 'logged-in-at').write_text((NOW - timedelta(days=23, hours=12)).isoformat())
    built.script.pages = [LOGGED_OUT, LOGGED_IN]

    # On `harry` itself: a server test earlier in the run may have left that logger at WARNING.
    with caplog.at_level(logging.INFO, logger='harry'):
        await article(built)

    assert any('the previous session lasted 23.5 days' in record.getMessage() for record in caplog.records)


@respx.mock
async def test_a_refused_login_is_one_attempt_and_one_line_for_five_articles(harry):
    feeds_are_up()
    built = harry()
    built.script.pages = [LOGGED_OUT]
    built.script.logins = [REFUSED]

    stories = built.news.search(source='tijd', limit=5, detail='full')['candidates']
    assert len({story['id'] for story in stories}) == 5

    answers = []
    for minutes, story in enumerate(stories):
        built.clock.now = NOW + timedelta(minutes=12 * minutes)
        answers.append(await article(built, story['id']))

    assert len(built.script.logged_in) == 1
    assert all(answer['available'] is False for answer in answers)
    assert len({answer['why'] for answer in answers}) == 1, 'every article in the wait gets the same answer'
    assert 'refused the email or password' in answers[0]['why']
    assert [answer['summary'] for answer in answers] == [story['summary'] for story in stories], 'each prints its own'
    assert built.sink.heard == [f'De Tijd: {answers[0]["why"]}']


@respx.mock
async def test_six_hours_after_a_refused_login_harry_tries_once_more(harry):
    feeds_are_up()
    built = harry()
    built.script.pages = [LOGGED_OUT]
    built.script.logins = [REFUSED]

    await article(built)
    built.clock.now = NOW + timedelta(hours=5, minutes=59)
    await article(built)
    assert len(built.script.logged_in) == 1

    built.clock.now = NOW + timedelta(hours=6, seconds=1)
    await article(built)
    assert len(built.script.logged_in) == 2


@respx.mock
async def test_a_login_page_that_did_not_answer_waits_fifteen_minutes_not_six_hours(harry):
    feeds_are_up()
    built = harry()
    built.script.pages = [LOGGED_OUT]
    built.script.logins = [built.failures().LoginUnreachable]

    first = await article(built)
    built.clock.now = NOW + timedelta(minutes=14)
    await article(built)
    assert len(built.script.logged_in) == 1

    built.clock.now = NOW + timedelta(minutes=15, seconds=1)
    await article(built)
    assert len(built.script.logged_in) == 2
    assert first['why'] == "Harry could not log in: De Tijd's homepage did not answer. Harry tries again in 15 minutes"


@respx.mock
async def test_a_captcha_is_reported_as_one(harry):
    feeds_are_up()
    built = harry()
    built.script.pages = [LOGGED_OUT]
    built.script.logins = [End('password', PASSWORD_STEP, page('login-captcha.html'))]

    answer = await article(built)

    assert 'such as a captcha' in answer['why']


@respx.mock
async def test_a_login_step_harry_does_not_know_is_named(harry):
    feeds_are_up()
    built = harry()
    built.script.pages = [LOGGED_OUT]
    built.script.logins = [End('email', 'https://auth.mediafin.be/u/login/identifier', page('login-unexpected.html'))]

    answer = await article(built)

    assert answer['why'].startswith('Harry could not log in: at the email step, the login page did not show')


@respx.mock
async def test_still_paywalled_after_a_login_points_at_the_subscription_and_does_not_log_in_again(harry):
    feeds_are_up()
    built = harry()
    built.script.pages = [LOGGED_OUT]

    first = await article(built)
    second = await article(built)

    assert first['why'] == 'Harry logged in, but De Tijd still shows the paywall. Check that the subscription is active'
    assert second['why'] == first['why']
    assert len(built.script.logged_in) == 1
    assert len(built.sink.heard) == 1


# ---------------------------------------------------------------------------
# The image, and the real site
# ---------------------------------------------------------------------------

IMAGE = 'harry:latest'


@pytest.fixture
def built_image():
    """Skips unless `harry:latest` is on this machine — it is not a tracked artefact."""
    if shutil.which('docker') is None:
        pytest.skip('docker is not installed here')
    if subprocess.run(['docker', 'image', 'inspect', IMAGE], capture_output=True).returncode != 0:
        pytest.skip(f'{IMAGE} has not been built here — run `make image` first')


@pytest.mark.live
def test_harry_s_own_login_reads_a_de_tijd_article_in_full_from_the_image(built_image, tmp_path):
    """The real connector, the real browser, the real login page — starting with no session.

    Depends on three things this repository does not track: a built image, a De Tijd account in
    this machine's `.harry/connectors/tijd/.env.local`, and tijd.be. It logs in once.
    """
    credentials = REPO / '.harry' / 'connectors' / 'tijd' / '.env.local'
    if not credentials.exists():
        pytest.skip('no De Tijd account in .harry/connectors/tijd/.env.local on this machine')
    probe = (
        'import json, sys, trafilatura\n'
        'from harry.loader import load\n'
        'found = load().get("connector", "tijd")\n'
        'assert found.status == "loaded", found.reason\n'
        'answer = found.target.read(sys.argv[1])\n'
        'text = trafilatura.extract(answer.get("html", ""), url=answer.get("url"), favor_precision=True) or ""\n'
        'print(json.dumps({"why": answer.get("why"), "chars": len(text), "session": sorted(p.name for p in __import__("pathlib").Path("/tmp/tijd").iterdir())}))\n'
    )
    link = feed_link()
    # Mounted where the real stack's settings directory would hold it, never copied: a second
    # copy of the password on disk is one more place for it to be left behind.
    ran = subprocess.run(
        [
            'docker',
            'run',
            '--rm',
            '-v',
            f'{credentials}:/settings/connectors/tijd/.env.local:ro',
            '-e',
            'HARRY_CAPABILITY_SETTINGS_DIR=/settings',
            '-e',
            'HARRY_TIJD_SESSION_DIR=/tmp/tijd',
            IMAGE,
            'uv',
            'run',
            'python',
            '-c',
            probe,
            link,
        ],
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert ran.returncode == 0, ran.stderr[-2000:]
    answer = json.loads(ran.stdout.strip().splitlines()[-1])
    assert answer['why'] is None, answer
    assert answer['chars'] > 1000, answer
    assert answer['session'] == ['logged-in-at', 'storage-state.json'], (
        'it logged in, from nothing, and kept the session'
    )


def feed_link() -> str:
    """Today's first De Tijd story, so the live test reads an article that still exists."""
    import xml.etree.ElementTree as ElementTree

    feed = httpx.get(TIJD_FEED, timeout=10).text
    link = ElementTree.fromstring(feed).findtext('.//item/link')
    assert link, 'De Tijd published no items'
    return link
