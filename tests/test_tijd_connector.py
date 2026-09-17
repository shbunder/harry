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
BACK_HOME = End('sent', HOME, '<html lang="nl"></html>')
REFUSED = End('sent', PASSWORD_STEP, page('login-refused.html'))


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
        self.on_saved_state: type[Exception] | None = None
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
        if self.on_saved_state is not None and self.opened_with[-1] is not None:
            raise self.on_saved_state('the browser refused the saved session')
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
        entry = self._next(self.logins)
        if isinstance(entry, Broke):
            self.login_step = entry.step
            raise entry.failure(f'net::ERR_CONNECTION_RESET {PASSWORD}')
        return self._play(entry)

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
    factory: Any = None
    """What `register()` bound the settings into, before the stand-in took its place."""

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
            built.factory = built.tijd._browser  # noqa: SLF001 — the real Chromium, as configured
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
    captcha = End('sent', PASSWORD_STEP, page('login-captcha.html'))
    assert pages_module(harry()).login_outcome(captcha) == 'challenge'


def test_a_page_that_neither_finished_nor_refused_is_a_login_page_harry_does_not_know(harry):
    """Including one whose script mentions captchas — a word is not an element."""
    unexpected = End('sent', PASSWORD_STEP, page('login-unexpected.html'))
    assert 'data-captcha-provider' in unexpected.html
    assert pages_module(harry()).login_outcome(unexpected) == 'login-page'


def test_a_login_that_stopped_before_the_password_was_sent_is_stalled_not_changed(harry):
    """Only a sent password ends a login, and only after one can a failure count towards a
    lockout. Before it, a slow page and a changed one look the same, and both are tried again soon."""
    rules = pages_module(harry())
    for step in ('open', 'email', 'password'):
        assert rules.login_outcome(End(step, HOME, '<html></html>')) == 'login-stalled', step
    assert rules.login_outcome(End('email', PASSWORD_STEP, page('login-refused.html'))) == 'refused'


def test_only_de_tijd_s_login_service_is_somewhere_to_type(harry):
    rules = pages_module(harry())
    assert rules.on_login_service('https://auth.mediafin.be/u/login/identifier?state=x')
    assert not rules.on_login_service('https://www.tijd.be/')
    assert not rules.on_login_service('https://auth.mediafin.be.example.com/u/login/identifier')


def test_no_fixture_a_logged_in_person_saw_carries_an_email_address(harry):
    """The login page carries the account's address twice: in the email field, and URL-encoded in
    its "forgot password" link. The first scrub caught one. This reads every encoding."""
    from urllib.parse import unquote

    address = __import__('re').compile(r'[A-Za-z0-9._%+-]+(?:@|%40|%2540|&#64;)([A-Za-z0-9.-]+\.[A-Za-z]{2,})', 2)
    for fixture in sorted(PAGES.iterdir()):
        domains = {unquote(match.group(1)).lower() for match in address.finditer(fixture.read_text(encoding='utf-8'))}
        assert domains <= {'example.com', 'de.tijd'}, f'{fixture.name} carries an address at {sorted(domains)}'


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

    def __init__(self, error: type[Exception], messages: list[Any]) -> None:
        self.error, self.messages, self.url, self.loads = error, messages, ARTICLE, 0
        self.timeouts: list[float] = []

    def goto(self, link: str, **options: Any) -> Any:
        self.loads += 1
        self.timeouts.append(options['timeout'])
        if self.messages:
            failure = self.messages.pop(0)
            raise failure if isinstance(failure, Exception) else self.error(failure)
        return type('Response', (), {'status': 200})()

    def content(self) -> str:
        return LOGGED_IN.html


def chromium_with(built: Harry, *messages: Any) -> tuple[Any, Interrupted]:
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


def test_a_page_that_does_not_arrive_within_its_thirty_seconds_did_not_load(harry):
    """Mapped to "did not load", never to "the browser could not start" — which would send
    whoever reads it to look at the display."""
    from playwright.sync_api import TimeoutError as PlaywrightTimeout

    built = harry()
    browser, page = chromium_with(built, PlaywrightTimeout('Timeout 30000ms exceeded'))

    with pytest.raises(built.failures().PageDidNotLoad):
        browser.visit(STUB, 30)
    assert len(page.timeouts) == 1 and 29_000 < page.timeouts[0] <= 30_000, page.timeouts


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


class Step:
    def __init__(self, page: LoginPage, selector: str) -> None:
        self.page, self.selector = page, selector

    @property
    def first(self) -> Step:
        return self

    def click(self, timeout: float) -> None:
        self.page.timeouts.append(timeout)
        self.page.act('click', self.selector)

    def fill(self, value: str, timeout: float) -> None:
        self.page.timeouts.append(timeout)
        self.page.act('fill', self.selector, value)

    def wait_for(self, state: str, timeout: float) -> None:
        self.page.timeouts.append(timeout)
        self.page.act('wait_for', self.selector)

    def is_visible(self) -> bool:
        return self.selector in self.page.visible


class LoginPage:
    """The page `Chromium.log_in` drives. Each action can be made to fail; the second submit,
    the password's, lands back on www.tijd.be."""

    def __init__(
        self, *, url: str = 'https://auth.mediafin.be/u/login/identifier', home: Any = 200, visible=(), failures=None
    ):
        self.url, self.home, self.visible = url, home, set(visible)
        self.failures = dict(failures or {})
        self.typed: list[str] = []
        self.submits = 0
        self.timeouts: list[float] = []

    def goto(self, link: str, **options: Any) -> Any:
        self.timeouts.append(options['timeout'])
        if isinstance(self.home, Exception):
            raise self.home
        return type('Response', (), {'status': self.home})()

    def get_by_role(self, role: str, name: str) -> Step:
        return Step(self, f'button:{name}')

    def locator(self, selector: str) -> Step:
        return Step(self, selector)

    def act(self, action: str, selector: str, value: str | None = None) -> None:
        failure = self.failures.get((action, selector))
        if failure is not None:
            raise failure
        if action == 'fill':
            self.typed.append(selector)
        if action == 'click' and selector.startswith('button[type=submit]'):
            self.submits += 1
            if self.submits == 2:
                self.url = HOME

    def wait_for_timeout(self, milliseconds: float) -> None:
        return None

    def wait_for_load_state(self, state: str, timeout: float) -> None:
        self.timeouts.append(timeout)
        failure = self.failures.get(('load', state))
        if failure is not None:
            raise failure

    def content(self) -> str:
        return '<html></html>'


def chromium_for(built: Harry, page: LoginPage) -> Any:
    """A `Chromium` driving a stand-in page. No cookie dialog unless a test puts one up."""
    from playwright.sync_api import TimeoutError as PlaywrightTimeout

    module = sys.modules[type(built.tijd).__module__ + '.browser']
    page.failures.setdefault(('wait_for', 'button:Optionele cookies weigeren'), PlaywrightTimeout('no dialog'))
    browser = module.Chromium(None)
    browser._page = page  # noqa: SLF001 — the page Chromium would drive
    browser._context = type('Context', (), {'clear_cookies': lambda self: None})()  # noqa: SLF001
    return browser


def logging_in(built: Harry, page: LoginPage, seconds: float = 0.3) -> Any:
    """`Chromium.log_in` against a stand-in page."""
    return chromium_for(built, page).log_in(EMAIL, PASSWORD, seconds)


LOGIN_FIELDS = {'#username', '#password'}


def test_a_login_through_both_steps_ends_back_on_de_tijd(harry):
    built = harry()
    page = LoginPage(visible=LOGIN_FIELDS)

    end = logging_in(built, page, seconds=5)

    assert page.typed == ['#username', '#password']
    assert pages_module(built).login_outcome(end) is None


def test_every_wait_in_a_login_fits_inside_the_login_s_one_budget(harry):
    built = harry()
    page = LoginPage(visible=LOGIN_FIELDS)

    logging_in(built, page, seconds=5)

    assert page.timeouts, 'nothing was waited for'
    # At least one millisecond: Playwright reads 0 as "wait forever".
    assert all(1 <= timeout <= 5_000 for timeout in page.timeouts), page.timeouts


def test_a_login_whose_fields_never_come_gives_up_when_its_budget_is_spent(harry):
    built = harry()
    started = time.monotonic()

    end = logging_in(built, LoginPage(visible=set()), seconds=0.5)

    assert end.step == 'open'
    assert time.monotonic() - started < 1.5, 'the login kept waiting past its budget'


def test_a_homepage_that_does_not_answer_is_unreachable_and_one_that_says_403_is_the_browser_refused(harry):
    from playwright.sync_api import Error, TimeoutError as PlaywrightTimeout

    built = harry()
    failures = built.failures()
    for home in (PlaywrightTimeout('Timeout 60000ms exceeded'), Error('net::ERR_NAME_NOT_RESOLVED')):
        with pytest.raises(failures.LoginUnreachable):
            logging_in(built, LoginPage(home=home))
    with pytest.raises(failures.Refused):
        logging_in(built, LoginPage(home=403))


def test_a_step_that_runs_out_of_time_reports_the_step_it_was_in(harry):
    from playwright.sync_api import TimeoutError as PlaywrightTimeout

    built = harry()
    rules = pages_module(built)
    button = LoginPage(failures={('click', '.trck_sitenav_login:visible'): PlaywrightTimeout('late')})
    assert logging_in(built, button).step == 'open'

    no_password_field = LoginPage(visible={'#username'})
    end = logging_in(built, no_password_field)
    assert end.step == 'email'
    assert no_password_field.typed == ['#username'], 'the password is never typed without its field'
    assert rules.login_outcome(end) == 'login-stalled'


STEP_LOST_AT = {
    ('fill', '#username'): 'email',
    ('fill', '#password'): 'password',
    ('click', 'button[type=submit][name="action"][value="default"]'): 'sent',
    ('load', 'load'): 'landed',
}
"""Where the browser is lost, and the step Chromium must say the login had reached. The submit
button's first click is the email's, so its failure is placed on the second, below."""


@pytest.mark.parametrize(('where', 'reached'), list(STEP_LOST_AT.items()), ids=list(STEP_LOST_AT.values()))
def test_a_login_the_browser_loses_part_way_remembers_the_step_it_had_reached(harry, where, reached):
    """How long the next login waits turns on this: only between the password's click and a
    landing back on De Tijd could a retry count towards a lockout."""
    from playwright.sync_api import Error

    built = harry()
    page = LoginPage(visible=LOGIN_FIELDS, failures={where: Error('Target page has been closed')})
    if where[0] == 'click':
        # Let the email's submit through, and lose the browser on the password's.
        failure = page.failures.pop(where)
        clicks = {'n': 0}
        act = page.act

        def second_submit_fails(action: str, selector: str, value: str | None = None) -> None:
            if action == 'click' and selector == where[1]:
                clicks['n'] += 1
                if clicks['n'] == 2:
                    raise failure
            act(action, selector, value)

        page.act = second_submit_fails  # type: ignore[method-assign]
    browser = chromium_for(built, page)

    with pytest.raises(built.failures().BrowserFailed):
        browser.log_in(EMAIL, PASSWORD, 5)
    assert browser.login_step == reached


def test_a_password_click_that_only_timed_out_was_never_sent(harry):
    from playwright.sync_api import TimeoutError as PlaywrightTimeout

    built = harry()
    page = LoginPage(visible=LOGIN_FIELDS)
    submit = 'button[type=submit][name="action"][value="default"]'
    act = page.act
    clicks = {'n': 0}

    def second_submit_times_out(action: str, selector: str, value: str | None = None) -> None:
        if action == 'click' and selector == submit:
            clicks['n'] += 1
            if clicks['n'] == 2:
                raise PlaywrightTimeout('Timeout exceeded')
        act(action, selector, value)

    page.act = second_submit_times_out  # type: ignore[method-assign]
    browser = chromium_for(built, page)

    end = browser.log_in(EMAIL, PASSWORD, 5)

    assert end.step == 'password' and browser.login_step == 'password'
    assert pages_module(built).login_outcome(end) == 'login-stalled'


def test_nothing_is_typed_on_a_page_that_is_not_the_login_service(harry):
    built = harry()
    elsewhere = LoginPage(url='https://ads.example.com/landing', visible=LOGIN_FIELDS)

    end = logging_in(built, elsewhere)

    assert elsewhere.typed == []
    assert end.step == 'open'


def test_an_error_carrying_the_typed_password_is_never_chained_onto_what_is_raised(harry):
    """Playwright's call log puts `fill("<value>")` into its error. A traceback printed later
    would print it, so the error raised in its place stands alone."""
    import traceback

    from playwright.sync_api import Error, TimeoutError as PlaywrightTimeout

    built = harry()
    crashed = LoginPage(
        visible=LOGIN_FIELDS, failures={('fill', '#password'): Error(f'fill("{PASSWORD}") — Target closed')}
    )
    with pytest.raises(built.failures().BrowserFailed) as raised:
        logging_in(built, crashed)
    printed = ''.join(traceback.format_exception(raised.value))
    assert PASSWORD not in printed

    slow = LoginPage(visible=LOGIN_FIELDS, failures={('fill', '#password'): PlaywrightTimeout(f'fill("{PASSWORD}")')})
    assert logging_in(built, slow).step == 'password', 'a password that was never sent is not a refusal'


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
async def test_nothing_harry_says_carries_the_email_or_the_password(harry, caplog):
    """Every failure the stand-in raises carries both in its message."""
    feeds_are_up()
    built = harry()
    failures = built.failures()
    said: list[str] = []
    with caplog.at_level(logging.DEBUG, logger='harry'):
        for minutes, playing in enumerate(
            (failures.BrowserFailed, failures.PageDidNotLoad, failures.Refused, RuntimeError)
        ):
            # Past each rest, so every failure is really read rather than answered from the last.
            built.clock.now = NOW + timedelta(minutes=11 * minutes)
            built.script.pages = [playing]
            said.append((await article(built))['why'])
        built.script.pages = [LOGGED_OUT]
        for hours, how in enumerate(
            (REFUSED, Broke(failures.BrowserFailed, 'sent'), Broke(failures.PageDidNotLoad, 'email'))
        ):
            # Past each login wait, so every login failure is really met.
            built.clock.now = NOW + timedelta(hours=7 * (hours + 1))
            built.script.logins = [how]
            said.append((await article(built))['why'])

    # Seven failures, six sentences: a surprise and a browser that stopped are told the same way.
    assert len(set(said)) == 6, said
    for text in [*said, *built.sink.heard, caplog.text]:
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
async def test_a_surprise_inside_a_read_costs_that_article_and_its_text_is_never_logged(harry, caplog):
    """The stand-in's error carries the password, as a Playwright `fill` error carries what it typed."""
    feeds_are_up()
    built = harry()
    built.script.pages = [RuntimeError]

    with caplog.at_level(logging.DEBUG, logger='harry'):
        answer = await article(built)

    assert answer['available'] is False
    assert answer['why'] == 'the browser Harry reads De Tijd with could not start, or stopped'
    assert built.sink.heard == [f'De Tijd: {answer["why"]}']
    assert 'RuntimeError' in caplog.text, 'the log says what kind of surprise it was'
    assert PASSWORD not in caplog.text and EMAIL not in caplog.text


@respx.mock
async def test_a_reader_that_raises_costs_that_article_and_news_says_so_without_a_traceback(harry, caplog):
    feeds_are_up()
    built = harry()

    def boom(link: str) -> dict:
        raise RuntimeError(f'fill("{PASSWORD}")')

    built.tijd.read = boom

    with caplog.at_level(logging.DEBUG, logger='harry'):
        answer = await article(built)

    assert answer['why'] == 'the connector that reads De Tijd failed (RuntimeError)'
    assert built.sink.heard == [f'De Tijd: {answer["why"]}']
    assert PASSWORD not in caplog.text


@respx.mock
async def test_a_reader_answering_neither_a_page_nor_a_why_is_a_failure_too(harry):
    feeds_are_up()
    built = harry()
    built.tijd.read = lambda link: {}

    answer = await article(built)

    assert answer['why'] == 'the connector that reads De Tijd failed (TypeError)'


@respx.mock
async def test_a_reader_that_cannot_say_which_links_are_its_own_costs_the_other_sources_nothing(harry, caplog):
    feeds_are_up()
    respx.get(url__startswith=TRAIN).mock(
        return_value=httpx.Response(200, text=(FEEDS / 'bbc-article.html').read_text())
    )
    built = harry()

    def boom(link: str) -> bool:
        raise RuntimeError('broken')

    built.tijd.handles = boom

    with caplog.at_level(logging.ERROR, logger='harry'):
        answer = await article(built, TRAIN_ID)

    assert answer['available'] is True
    assert 'could not say whether it reads a link' in caplog.text


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


@respx.mock
async def test_a_saved_session_the_browser_refuses_is_set_aside_and_the_read_goes_on(harry, caplog):
    feeds_are_up()
    built = harry()
    built.session.mkdir(parents=True)
    saved = built.session / 'storage-state.json'
    saved.write_text(json.dumps({'cookies': [{'name': 'from-an-older-browser'}], 'origins': []}))
    built.script.on_saved_state = built.failures().BrowserFailed

    with caplog.at_level(logging.WARNING, logger='harry'):
        answer = await article(built)

    assert answer['available'] is True
    assert built.script.opened_with == [saved, None]
    assert 'would not start with the saved De Tijd session' in caplog.text
    assert built.sink.heard == []


def test_a_read_that_does_not_come_back_is_given_up_on_and_nothing_queues_behind_it(harry, monkeypatch):
    """A renderer wedged in an ad script holds a Playwright call with no timeout of its own.

    Once a read is known stuck, the next is answered at once: queueing behind it would spend that
    call's own limit waiting, and a page with two De Tijd stories would outlast its client.
    """
    built = harry()
    monkeypatch.setattr(built.failures(), 'READ_SECONDS', 0.3)
    built.script.pause = 1.5

    stuck = built.tijd.read(STUB)
    built.script.pause = 0.0
    built.clock.now = NOW + timedelta(minutes=11)  # past the rest, so only the stuck read answers
    started = time.monotonic()
    busy = built.tijd.read(STUB)
    waited = time.monotonic() - started
    time.sleep(1.5)
    fine = built.tijd.read(STUB)

    assert stuck['why'] == 'reading the article took longer than 150 seconds, so Harry stopped waiting for it'
    assert busy['why'] == 'an earlier De Tijd article is still stuck in the browser, so this one was not read'
    assert waited < 0.1, f'the article behind a stuck read waited {waited:.2f}s instead of being answered at once'
    assert 'html' in fine, 'the stuck read came back, and the browser is free again'
    assert len(built.sink.heard) == 2


def test_a_read_arriving_while_another_hangs_waits_no_longer_than_the_limit(harry, monkeypatch):
    """Before the hanging read is declared stuck, the next one queues for the lock — and only the
    lock's own timeout stops that queue lasting as long as the hang."""
    built = harry()
    monkeypatch.setattr(built.failures(), 'READ_SECONDS', 1.0)
    built.script.pause = 3.0
    first = threading.Thread(target=built.tijd.read, args=(STUB,))
    first.start()
    time.sleep(0.1)

    started = time.monotonic()
    second = built.tijd.read(STUB)
    waited = time.monotonic() - started
    first.join()

    assert second['why'] == 'an earlier De Tijd article is still stuck in the browser, so this one was not read'
    assert 0.7 < waited < 1.6, f'the second read waited {waited:.2f}s against a limit of 1s'


def test_the_hard_limit_is_the_sum_of_the_waits_harry_sets(harry):
    """Reaching the browser, two pages and a login. The first term is the wait on the browser
    container, so raising that must raise this or a read can outlast the limit that catches it."""
    built = harry()
    module = built.failures()
    reaching = chromium_module(built).CONNECT_SECONDS

    assert module.READ_SECONDS == reaching + 2 * module.PAGE_SECONDS + module.LOGIN_SECONDS == 150


@respx.mock
async def test_after_a_failure_that_cost_time_de_tijd_rests_for_ten_minutes(harry):
    """A tool call silent for 300 seconds is abandoned, and the morning page reads every story it
    chose inside one. After one slow failure, the rest of its De Tijd stories answer at once."""
    feeds_are_up()
    built = harry()
    built.script.pages = [built.failures().PageDidNotLoad, LOGGED_IN]

    first = await article(built)
    built.clock.now = NOW + timedelta(minutes=9, seconds=59)
    resting = await article(built)
    assert built.script.visited == [STUB], 'the browser was tried again inside the rest'
    assert resting['why'] == first['why']
    assert len(built.sink.heard) == 1

    built.clock.now = NOW + timedelta(minutes=10, seconds=1)
    after = await article(built)
    assert after['available'] is True


@respx.mock
async def test_a_failure_that_cost_no_time_is_not_rested_on(harry):
    feeds_are_up()
    built = harry()
    built.script.pages = [Visit(403, ARTICLE, '<html></html>'), LOGGED_IN]

    await article(built)
    after = await article(built)

    assert after['available'] is True
    assert built.script.visited == [STUB, STUB]


def test_the_tijd_connector_s_own_lines_have_its_email_and_password_scrubbed(harry):
    """The fixed sentences carry neither. This is the net under them: the declaration marks both
    secret, so a line that did carry them would be scrubbed on its way to Slack."""
    built = harry()
    context = built.catalogue.get('connector', 'tijd').context

    context.alert(f'refused {EMAIL} with {PASSWORD}', key='probe')

    assert built.sink.heard == ['refused [redacted] with [redacted]']


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


@dataclass(frozen=True)
class Broke:
    """A login the browser or the network ended part-way, having reached `step`."""

    failure: Any
    step: str


def ending(built: Harry, how: Any) -> Any:
    """A login ending for `Script.logins`, with the connector's own exception classes filled in."""
    if isinstance(how, Broke):
        return Broke(getattr(built.failures(), how.failure), how.step)
    if isinstance(how, str):
        return getattr(built.failures(), how)
    return how


SIX_HOURS = {
    'refused': (REFUSED, 'refused the email or password'),
    'challenge': (End('sent', PASSWORD_STEP, page('login-captcha.html')), 'such as a captcha'),
    'login-page': (
        End('sent', PASSWORD_STEP, page('login-unexpected.html')),
        'after the password was sent, the login page did not show',
    ),
    'login-broke-sent': (Broke('BrowserFailed', 'sent'), 'cannot tell whether De Tijd accepted it'),
}
"""Every login failure after which a retry could count towards De Tijd blocking the account."""

FIFTEEN_MINUTES = {
    'login-unreachable': ('LoginUnreachable', "De Tijd's homepage did not answer"),
    'login-stalled': (
        End('email', 'https://auth.mediafin.be/u/login/identifier', page('login-unexpected.html')),
        'at the email step, the login page did not show what Harry expects in time',
    ),
    'login-broke': (Broke('PageDidNotLoad', 'email'), 'the browser or the network failed at the email step'),
}
"""Every login failure in which the password was never sent, so a retry cannot lock anything."""


WHOLE_SENTENCES = {
    End('open', HOME, '<html></html>'): (
        'Harry could not log in: at the start of the login, the login page did not show what Harry expects '
        'in time. It may be slow, or De Tijd may have changed it. Harry tries again in 15 minutes'
    ),
    End('email', 'https://auth.mediafin.be/u/login/identifier', '<html></html>'): (
        'Harry could not log in: at the email step, the login page did not show what Harry expects in time. '
        'It may be slow, or De Tijd may have changed it. Harry tries again in 15 minutes'
    ),
    End('sent', PASSWORD_STEP, page('login-unexpected.html')): (
        'Harry could not log in: after the password was sent, the login page did not show what Harry expects, '
        'so De Tijd may have added a step, such as a code. Harry waits 6 hours before trying again'
    ),
    Broke('BrowserFailed', 'landed'): (
        'Harry could not log in: the browser or the network failed after De Tijd took the password. Nothing '
        'was refused, so Harry tries again in 15 minutes'
    ),
}
"""What a person reads over coffee, in full, for each step a login can stop in."""


@pytest.mark.parametrize('how', list(WHOLE_SENTENCES), ids=['open', 'email', 'sent', 'landed'])
@respx.mock
async def test_each_login_step_reads_as_a_sentence(harry, how):
    feeds_are_up()
    built = harry()
    built.script.pages = [LOGGED_OUT]
    built.script.logins = [ending(built, how)]

    answer = await article(built)

    assert answer['why'] == WHOLE_SENTENCES[how]


@pytest.mark.parametrize('reason', sorted(SIX_HOURS))
@respx.mock
async def test_after_a_failure_that_could_count_towards_a_lockout_harry_waits_six_hours(harry, reason):
    how, said = SIX_HOURS[reason]
    feeds_are_up()
    built = harry()
    built.script.pages = [LOGGED_OUT]
    built.script.logins = [ending(built, how)]

    first = await article(built)
    built.clock.now = NOW + timedelta(hours=5, minutes=59)
    second = await article(built)
    assert len(built.script.logged_in) == 1, 'a second attempt inside the six hours'
    assert said in first['why']
    assert 'Harry waits 6 hours before trying again' in first['why']
    assert second['why'] == first['why']

    built.clock.now = NOW + timedelta(hours=6, seconds=1)
    await article(built)
    assert len(built.script.logged_in) == 2, 'no attempt once the six hours are up'


@pytest.mark.parametrize('reason', sorted(FIFTEEN_MINUTES))
@respx.mock
async def test_after_a_failure_that_sent_no_password_harry_tries_again_in_fifteen_minutes(harry, reason):
    """A slow homepage at 06:30 must not cost De Tijd until noon."""
    how, said = FIFTEEN_MINUTES[reason]
    feeds_are_up()
    built = harry()
    built.script.pages = [LOGGED_OUT]
    built.script.logins = [ending(built, how)]

    first = await article(built)
    built.clock.now = NOW + timedelta(minutes=14)
    await article(built)
    assert len(built.script.logged_in) == 1

    built.clock.now = NOW + timedelta(minutes=15, seconds=1)
    await article(built)
    assert len(built.script.logged_in) == 2
    assert said in first['why']
    assert first['why'].endswith('Harry tries again in 15 minutes')


@respx.mock
async def test_a_captcha_is_reported_as_one(harry):
    feeds_are_up()
    built = harry()
    built.script.pages = [LOGGED_OUT]
    built.script.logins = [End('password', PASSWORD_STEP, page('login-captcha.html'))]

    answer = await article(built)

    assert 'such as a captcha' in answer['why']


@respx.mock
async def test_still_paywalled_after_a_login_points_at_the_subscription_and_does_not_log_in_again(harry):
    feeds_are_up()
    built = harry()
    built.script.pages = [LOGGED_OUT]

    first = await article(built)
    built.clock.now = NOW + timedelta(hours=5, minutes=59)
    second = await article(built)

    assert first['why'] == 'Harry logged in, but De Tijd still shows the paywall. Check that the subscription is active'
    assert second['why'] == first['why']
    assert len(built.script.logged_in) == 1
    assert len(built.sink.heard) == 1

    built.clock.now = NOW + timedelta(hours=6, seconds=1)
    await article(built)
    assert len(built.script.logged_in) == 2, 'the wait after a paywall is six hours, not longer'


# ---------------------------------------------------------------------------
# Where the browser runs
# ---------------------------------------------------------------------------

ENDPOINT = 'ws://harry-browser:3000/'


class Elsewhere:
    """Playwright, with the browser somewhere else. Records how it was asked for one."""

    def __init__(self, refuse: Exception | None = None) -> None:
        self.connected: list[tuple[str, float | None]] = []
        self.launched: list[dict] = []
        self.refuse = refuse

    def start(self) -> Elsewhere:
        return self

    def stop(self) -> None:
        return None

    @property
    def chromium(self) -> Elsewhere:
        return self

    def connect(self, url: str, timeout: float | None = None) -> Elsewhere:
        self.connected.append((url, timeout))
        if self.refuse is not None:
            raise self.refuse
        return self

    def launch(self, **options: Any) -> Elsewhere:
        self.launched.append(options)
        return self

    def new_context(self, **_: Any) -> Elsewhere:
        return self

    def new_page(self) -> Elsewhere:
        return self

    def close(self) -> None:
        return None


def chromium_module(built: Harry) -> Any:
    return sys.modules[type(built.tijd).__module__ + '.browser']


def opened(built: Harry, endpoint: str, monkeypatch, refuse: Exception | None = None) -> Elsewhere:
    module = chromium_module(built)
    playwright = Elsewhere(refuse)
    monkeypatch.setattr(module, 'sync_playwright', lambda: playwright)
    browser = module.Chromium(None, endpoint)
    if refuse is None:
        with browser:
            pass
    else:
        with pytest.raises(built.failures().BrowserFailed), browser:
            pass
    return playwright


def test_with_an_endpoint_the_browser_is_the_one_in_its_own_container(harry, monkeypatch):
    """The container that holds no credential. Harry starts none of its own beside the keys."""
    built = harry()

    playwright = opened(built, ENDPOINT, monkeypatch)

    assert playwright.launched == [], 'a browser was started inside Harry anyway'
    assert len(playwright.connected) == 1
    url, timeout = playwright.connected[0]
    assert url.startswith(ENDPOINT)
    assert timeout == 30_000


def test_the_connect_url_asks_for_a_headed_sandboxed_full_chromium_every_time(harry):
    """Measured: a browser container asked for nothing launches headless, and De Tijd answers 403.
    The sandbox is the point of the separate container, and the headless shell is refused outright."""
    from urllib.parse import parse_qs, urlsplit

    module = chromium_module(harry())
    asked = json.loads(parse_qs(urlsplit(module.connect_to(ENDPOINT)).query)['launch-options'][0])

    assert asked == {'headless': False, 'channel': 'chromium', 'chromiumSandbox': True}


def test_with_no_endpoint_harry_starts_a_browser_itself(harry, monkeypatch):
    """A laptop, `make serve`, the live tests. Unsandboxed, because Chromium's sandbox will not
    start under Docker's default seccomp and relaxing that beside the credentials is the thing
    the browser container exists to avoid."""
    built = harry()

    playwright = opened(built, '', monkeypatch)

    assert playwright.connected == []
    assert playwright.launched == [{'headless': False, 'channel': 'chromium', 'chromium_sandbox': False}]


@respx.mock
async def test_a_browser_container_that_is_not_there_costs_de_tijd_and_nothing_else(harry, monkeypatch):
    feeds_are_up()
    respx.get(url__startswith=TRAIN).mock(
        return_value=httpx.Response(200, text=(FEEDS / 'bbc-article.html').read_text())
    )
    built = harry()
    module = chromium_module(built)
    from playwright.sync_api import Error

    playwright = Elsewhere(Error('connect: WebSocket error'))
    monkeypatch.setattr(module, 'sync_playwright', lambda: playwright)
    built.tijd._browser = lambda state: module.Chromium(state, ENDPOINT)  # noqa: SLF001 — the real one, pointed elsewhere

    tijd = await article(built)
    bbc = await article(built, TRAIN_ID)

    assert tijd['available'] is False
    assert tijd['why'] == 'the browser Harry reads De Tijd with could not start, or stopped'
    assert bbc['available'] is True
    assert built.sink.heard == [f'De Tijd: {tijd["why"]}']
    assert playwright.launched == [], 'Harry started a browser of its own, beside every credential'


def test_the_connector_is_handed_the_endpoint_its_settings_name(harry, monkeypatch):
    """Through `load()`: the setting reaches the browser the connector opens, or nothing does."""
    monkeypatch.setenv('HARRY_TIJD_BROWSER_ENDPOINT', ENDPOINT)
    built = harry()
    module = chromium_module(built)
    playwright = Elsewhere()
    monkeypatch.setattr(module, 'sync_playwright', lambda: playwright)

    with built.factory(None):
        pass

    assert [url for url, _ in playwright.connected] == [module.connect_to(ENDPOINT)]


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


def shipped_browser_flags() -> tuple[list[str], list[str]]:
    """What `docker-compose.yml` gives the browser container, as `docker run` arguments.

    Read from the compose file rather than repeated here: a live test that proved a configuration
    nobody deploys would be worth nothing, and `--unsafe` is exactly the kind of argument that
    would otherwise be in one place and not the other.
    """
    import yaml

    service = yaml.safe_load((REPO / 'docker-compose.yml').read_text(encoding='utf-8'))['services']['harry-browser']
    flags = ['--user', service['user'], '--read-only', '--pids-limit', str(service['pids_limit'])]
    for option in service.get('security_opt') or []:
        flags += ['--security-opt', option.replace(':', '=', 1)]
    for capability in service.get('cap_drop') or []:
        flags += ['--cap-drop', capability]
    for mount in service.get('tmpfs') or []:
        flags += ['--tmpfs', mount]
    for key, value in (service.get('environment') or {}).items():
        flags += ['--env', f'{key}={value}']
    return flags, list(service['command'])


def running_processes(container: str) -> str:
    """Every process in a container, by its command line.

    `ps` is not in this image. An earlier version of this test asked for it anyway, got an empty
    string back, and passed against a browser that was running with no sandbox at all.
    """
    read = subprocess.run(
        ['docker', 'exec', container, 'sh', '-c', 'for p in /proc/[0-9]*; do tr "\\0" " " < $p/cmdline; echo; done'],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert read.returncode == 0, read.stderr[-500:]
    assert read.stdout.strip(), 'nothing came back, so this proves nothing'
    return read.stdout


@pytest.mark.live
def test_harry_s_own_browser_wrapper_drives_a_sandboxed_browser_in_its_own_container(built_image):
    """The whole arrangement as it ships, against the real site, with no account needed.

    De Tijd's homepage answers 403 to a headless browser, so 200 proves headed. The sandbox is
    read from the browser's own processes **while a page is open** — measured 2026-09-17: the
    server drops the sandbox the connect URL asks for unless it was started with `--unsafe`, and
    11 of 13 Chromium processes then carry `--no-sandbox`.
    """
    flags, command = shipped_browser_flags()
    assert '--unsafe' in command, 'without it the server silently ignores the sandbox it is asked for'
    network, browser, holder = 'tijd-public-net', 'tijd-public-browser', 'tijd-public-holder'
    subprocess.run(['docker', 'network', 'create', network], capture_output=True)
    for name in (browser, holder):
        subprocess.run(['docker', 'rm', '-f', name], capture_output=True)
    try:
        started = subprocess.run(
            ['docker', 'run', '-d', '--name', browser, '--network', network, *flags, IMAGE, *command],
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert started.returncode == 0, started.stderr[-2000:]
        for _ in range(30):
            if 'Listening on' in subprocess.run(['docker', 'logs', browser], capture_output=True, text=True).stdout:
                break
            time.sleep(1)

        # A page held open, so the browser exists while its processes are read — and opened by
        # Harry's own wrapper, so the launch options under test are the ones the connector states.
        holding = (
            'import sys, time\n'
            'import importlib.util\n'
            'spec = importlib.util.spec_from_file_location("t", "/app/.harry/connectors/tijd/connector.py", '
            'submodule_search_locations=["/app/.harry/connectors/tijd"])\n'
            'module = importlib.util.module_from_spec(spec)\n'
            'sys.modules["t"] = module\n'
            'spec.loader.exec_module(module)\n'
            'with module.Chromium(None, sys.argv[1]) as browser:\n'
            '    visit = browser.visit("https://www.tijd.be/", 45)\n'
            '    print(visit.status, flush=True)\n'
            '    time.sleep(45)\n'
        )
        subprocess.run(
            [
                'docker',
                'run',
                '-d',
                '--name',
                holder,
                '--network',
                network,
                IMAGE,
                'uv',
                'run',
                'python',
                '-c',
                holding,
                f'ws://{browser}:3000/',
            ],
            capture_output=True,
            text=True,
            timeout=120,
            check=True,
        )
        for _ in range(60):
            if subprocess.run(['docker', 'logs', holder], capture_output=True, text=True).stdout.strip():
                break
            time.sleep(1)
        answered = subprocess.run(['docker', 'logs', holder], capture_output=True, text=True).stdout.strip()
        assert answered == '200', f'De Tijd answered {answered!r}, which is what it does to a headless browser'

        processes = running_processes(browser)
        chromium = [line for line in processes.splitlines() if 'chrome' in line]
        assert len(chromium) > 1, f'no browser was running to inspect: {processes[:400]}'
        assert [line for line in chromium if '--type=renderer' in line], 'no renderer among them'
        unsandboxed = [line for line in chromium if '--no-sandbox' in line]
        assert unsandboxed == [], f'{len(unsandboxed)} of {len(chromium)} browser processes run with no sandbox'

        settings = subprocess.run(['docker', 'exec', browser, 'ls', '/settings'], capture_output=True, text=True)
        assert settings.returncode != 0, 'the browser container can see a settings directory'
    finally:
        for name in (holder, browser):
            subprocess.run(['docker', 'rm', '-f', name], capture_output=True)
        subprocess.run(['docker', 'network', 'rm', network], capture_output=True)


@pytest.mark.live
def test_de_tijd_reads_through_a_browser_container_that_holds_no_credential(built_image, tmp_path):
    """The whole arrangement, in two containers, against the real site.

    A browser container with nothing mounted, unprivileged and sandboxed, and a second container
    holding only this machine's De Tijd login. Depends on a built image, a De Tijd account and
    tijd.be. It logs in once.
    """
    credentials = REPO / '.harry' / 'connectors' / 'tijd' / '.env.local'
    if not credentials.exists():
        pytest.skip('no De Tijd account in .harry/connectors/tijd/.env.local on this machine')
    network, browser = 'tijd-live-net', 'tijd-live-browser'
    subprocess.run(['docker', 'network', 'create', network], capture_output=True)
    subprocess.run(['docker', 'rm', '-f', browser], capture_output=True)
    try:
        flags, command = shipped_browser_flags()
        started = subprocess.run(
            ['docker', 'run', '-d', '--name', browser, '--network', network, *flags, IMAGE, *command],
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert started.returncode == 0, started.stderr[-2000:]
        for _ in range(30):
            if 'Listening on' in subprocess.run(['docker', 'logs', browser], capture_output=True, text=True).stdout:
                break
            time.sleep(1)

        who = subprocess.run(['docker', 'exec', browser, 'id', '-u'], capture_output=True, text=True, timeout=60)
        assert who.stdout.strip() == '1000', f'the browser container runs as {who.stdout.strip()}'
        settings = subprocess.run(['docker', 'exec', browser, 'ls', '/settings'], capture_output=True, text=True)
        assert settings.returncode != 0, 'the browser container can see a settings directory'

        probe = (
            'import json, sys, trafilatura\n'
            'from harry.loader import load\n'
            'found = load().get("connector", "tijd")\n'
            'assert found.status == "loaded", found.reason\n'
            'answer = found.target.read(sys.argv[1])\n'
            'text = trafilatura.extract(answer.get("html", ""), url=answer.get("url"), favor_precision=True) or ""\n'
            'print(json.dumps({"why": answer.get("why"), "chars": len(text)}))\n'
        )
        ran = subprocess.run(
            [
                'docker',
                'run',
                '--rm',
                '--network',
                network,
                '-v',
                f'{credentials}:/settings/connectors/tijd/.env.local:ro',
                '-e',
                'HARRY_CAPABILITY_SETTINGS_DIR=/settings',
                '-e',
                'HARRY_TIJD_SESSION_DIR=/tmp/tijd',
                '-e',
                f'HARRY_TIJD_BROWSER_ENDPOINT=ws://{browser}:3000/',
                IMAGE,
                'uv',
                'run',
                'python',
                '-c',
                probe,
                feed_link(),
            ],
            capture_output=True,
            text=True,
            timeout=300,
        )
        assert ran.returncode == 0, ran.stderr[-2000:]
        answer = json.loads(ran.stdout.strip().splitlines()[-1])
        assert answer['why'] is None, answer
        assert answer['chars'] > 1000, answer

    finally:
        subprocess.run(['docker', 'rm', '-f', browser], capture_output=True)
        subprocess.run(['docker', 'network', 'rm', network], capture_output=True)


def feed_link() -> str:
    """Today's first De Tijd story, so the live test reads an article that still exists."""
    import xml.etree.ElementTree as ElementTree

    feed = httpx.get(TIJD_FEED, timeout=10).text
    link = ElementTree.fromstring(feed).findtext('.//item/link')
    assert link, 'De Tijd published no items'
    return link
