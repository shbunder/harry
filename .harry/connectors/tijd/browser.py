"""The browser De Tijd is read with: a headed Chromium, drawn on the virtual display.

**Headed, and the full Chromium.** Measured from Harry's image on 2026-09-16 against De Tijd's
homepage: `chrome-headless-shell` 403, full Chromium headless 403, headed Chromium under Xvfb
200. Full headless had been served three days earlier, so the edge tightens; a 403 here is
reported as the browser being refused, never as a lapsed login.

One browser per call, closed at the end. Nothing is kept running between calls: a morning
reads a handful of De Tijd stories, and a browser left open for a day is one more thing that
can wedge.

This file is what `make test-live` runs against the real site. Everything it decides — whether
a page is paywalled, how a login ended — is in `pages.py`, where recorded pages test it.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from playwright.sync_api import Error as PlaywrightError, TimeoutError as PlaywrightTimeout, sync_playwright

from .pages import CONSENT_REFUSE, EMAIL_FIELD, HOME, LANDED, LOGIN_BUTTON, PASSWORD_FIELD, REFUSALS, SUBMIT, LoginEnd

VIEWPORT = {'width': 1280, 'height': 900}

CONSENT_APPEARS = 5.0
"""Seconds to wait for the cookie dialog before deciding there is none. A saved session that
already answered it never sees it again."""

POLL = 0.25
"""Seconds between looks while waiting for one of a step's endings."""


class BrowserFailed(Exception):
    """The browser would not start, or stopped. Not De Tijd's doing."""


class PageDidNotLoad(Exception):
    """The page did not arrive in time, or could not be reached at all."""


class Refused(Exception):
    """De Tijd answered 403 — its bot filter turned the browser away."""


class LoginUnreachable(Exception):
    """The login could not even begin: De Tijd's homepage did not answer."""


@dataclass(frozen=True)
class Visit:
    """One page, as the browser ended up with it."""

    status: int | None
    url: str
    html: str


class Chromium:
    """A headed Chromium carrying a saved session, for the length of one `with` block."""

    def __init__(self, state: Path | None) -> None:
        self._state = state
        self._playwright: Any = None
        self._browser: Any = None
        self._context: Any = None
        self._page: Any = None

    def __enter__(self) -> Chromium:
        try:
            self._playwright = sync_playwright().start()
            # `channel='chromium'` is the full browser rather than the stripped headless shell,
            # which De Tijd refuses on every URL with a perfectly good session attached.
            self._browser = self._playwright.chromium.launch(headless=False, channel='chromium')
            self._context = self._browser.new_context(
                viewport=VIEWPORT, storage_state=str(self._state) if self._state else None
            )
            self._page = self._context.new_page()
        except PlaywrightError as error:
            self.__exit__(None, None, None)
            raise BrowserFailed(type(error).__name__) from error
        return self

    def __exit__(self, *_: object) -> None:
        for part, closing in ((self._context, 'close'), (self._browser, 'close'), (self._playwright, 'stop')):
            if part is None:
                continue
            try:
                getattr(part, closing)()
            except Exception:  # noqa: BLE001, S112 — closing a browser that already died is not a second fault
                continue

    def visit(self, link: str, seconds: float) -> Visit:
        """Open a page and hand back what arrived. A redirect stub is followed like any link.

        **Tried once more when the page's own navigation interrupted it** (`net::ERR_ABORTED`):
        a redirect still finishing when the next page is asked for abandons that page, and
        nothing about the article is wrong. Once, because a second abort is not a race.
        """
        deadline = time.monotonic() + seconds
        for attempt in (1, 2):
            try:
                response = self._page.goto(link, wait_until='domcontentloaded', timeout=_left(deadline))
                return Visit(response.status if response else None, self._page.url, self._page.content())
            except PlaywrightTimeout as error:
                raise PageDidNotLoad('timeout') from error
            except PlaywrightError as error:
                if attempt == 1 and 'net::ERR_ABORTED' in str(error):
                    continue
                raise self._why_it_failed(error) from error
        raise PageDidNotLoad('aborted')  # pragma: no cover — the loop always returns or raises

    def storage_state(self) -> dict[str, Any]:
        """The session as it stands now — renewed cookies included."""
        try:
            return self._context.storage_state()
        except PlaywrightError as error:
            raise BrowserFailed(type(error).__name__) from error

    def log_in(self, email: str, password: str, seconds: float) -> LoginEnd:
        """The login, step by step, stopping at the first step that does not end as expected.

        | Step | Does | Expected ending |
        |---|---|---|
        | open | answers the cookie dialog if shown, clicks Log in on the homepage | the email field |
        | email | fills it, submits | the password field, or an error on the email |
        | password | fills it, submits | back on www.tijd.be, or an error on the password |

        The whole login shares one budget of `seconds`. Neither value is ever logged or put in
        an error — a Playwright timeout names the selector it waited for, not what was typed.
        """
        deadline = time.monotonic() + seconds
        page = self._page
        try:
            # From no session at all. A session that is logged in but not subscribed shows no
            # Log in button, and would read as a login page that changed rather than as what
            # it is — which the second look at the article then says plainly.
            self._context.clear_cookies()
            response = page.goto(HOME, wait_until='domcontentloaded', timeout=_left(deadline))
        except PlaywrightTimeout as error:
            raise LoginUnreachable('timeout') from error
        except PlaywrightError as error:
            failure = self._why_it_failed(error)
            raise (LoginUnreachable(str(failure)) if isinstance(failure, PageDidNotLoad) else failure) from error
        if response is not None and response.status == 403:
            raise Refused('403')

        step = 'open'
        try:
            self._answer_cookies(deadline)
            page.locator(LOGIN_BUTTON).first.click(timeout=_left(deadline))
            if not self._first_of(deadline, email_field=EMAIL_FIELD):
                return self._stopped(step)
            step = 'email'
            page.locator(EMAIL_FIELD).fill(email, timeout=_left(deadline))
            page.locator(SUBMIT).first.click(timeout=_left(deadline))
            if self._first_of(deadline, password_field=PASSWORD_FIELD, **_refusals()) != 'password_field':
                return self._stopped(step)
            step = 'password'
            page.locator(PASSWORD_FIELD).fill(password, timeout=_left(deadline))
            page.locator(SUBMIT).first.click(timeout=_left(deadline))
            if self._first_of(deadline, landed=LANDED, **_refusals()) == 'landed':
                page.wait_for_load_state('load', timeout=_left(deadline))
            return self._stopped(step)
        except PlaywrightTimeout:
            return self._stopped(step)
        except PlaywrightError as error:
            raise self._why_it_failed(error) from error

    # -- the parts ------------------------------------------------------------

    def _answer_cookies(self, deadline: float) -> None:
        refuse = self._page.get_by_role('button', name=CONSENT_REFUSE).first
        try:
            refuse.wait_for(state='visible', timeout=min(CONSENT_APPEARS * 1000, _left(deadline)))
        except PlaywrightTimeout:
            return
        refuse.click(timeout=_left(deadline))

    def _first_of(self, deadline: float, **endings: str | re.Pattern[str]) -> str | None:
        """Which of these endings arrived first — a visible element, or a URL — or None."""
        while time.monotonic() < deadline:
            for name, ending in endings.items():
                if isinstance(ending, re.Pattern):
                    if ending.search(self._page.url):
                        return name
                elif self._page.locator(ending).first.is_visible():
                    return name
            self._page.wait_for_timeout(POLL * 1000)
        return None

    def _stopped(self, step: str) -> LoginEnd:
        """The page the login stopped on. A page mid-navigation has no content yet; wait once."""
        for _ in range(2):
            try:
                return LoginEnd(step, self._page.url, self._page.content())
            except PlaywrightError:
                self._page.wait_for_timeout(500)
        return LoginEnd(step, self._page.url, '')

    @staticmethod
    def _why_it_failed(error: PlaywrightError) -> Exception:
        """A navigation the network failed (`net::ERR_…`) is the page's; anything else is the browser's."""
        if 'net::ERR_' in str(error):
            return PageDidNotLoad('unreachable')
        return BrowserFailed(type(error).__name__)


def _left(deadline: float) -> float:
    """Milliseconds until the deadline, never less than one — Playwright reads 0 as "forever"."""
    return max(1.0, (deadline - time.monotonic()) * 1000)


def _refusals() -> dict[str, str]:
    return {refusal: f'#{refusal}' for refusal in REFUSALS}
