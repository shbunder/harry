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

from .pages import (
    CONSENT_REFUSE,
    EMAIL_FIELD,
    HOME,
    LANDED,
    LOGIN_BUTTON,
    PASSWORD_FIELD,
    REFUSALS,
    SUBMIT,
    LoginEnd,
    on_login_service,
)

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
        self.login_step = 'open'
        """The step the last login reached, kept for a failure that raises part-way: whether the
        password was already sent decides how long the next login waits."""

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
            raise BrowserFailed(type(error).__name__) from None
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
            except PlaywrightTimeout:
                raise PageDidNotLoad('timeout') from None
            except PlaywrightError as error:
                if attempt == 1 and 'net::ERR_ABORTED' in str(error):
                    continue
                raise self._why_it_failed(error) from None
        raise PageDidNotLoad('aborted')  # pragma: no cover — the loop always returns or raises

    def storage_state(self) -> dict[str, Any]:
        """The session as it stands now — renewed cookies included."""
        try:
            return self._context.storage_state()
        except PlaywrightError as error:
            raise BrowserFailed(type(error).__name__) from None

    def log_in(self, email: str, password: str, seconds: float) -> LoginEnd:
        """The login, step by step, stopping at the first step that does not end as expected.

        | Step | Does | Expected ending |
        |---|---|---|
        | open | answers the cookie dialog if shown, clicks Log in on the homepage | the email field, on auth.mediafin.be |
        | email | fills it, submits | the password field on auth.mediafin.be, or an error on the email |
        | password | fills it, submits — and is `sent` from then on | back on www.tijd.be, or an error on the password |

        The whole login shares one budget of `seconds`. **Nothing is typed anywhere but De Tijd's
        login service**: a page the Log in click did not lead there does not get the email, let
        alone the password.

        Playwright's own errors are never chained onto what this raises. A failed `fill` puts
        the value it was typing into its call log, and a traceback printed later would print it.
        """
        deadline = time.monotonic() + seconds
        page = self._page
        self.login_step = 'open'
        try:
            # From no session at all. A session that is logged in but not subscribed shows no
            # Log in button, and would read as a login page that changed rather than as what
            # it is — which the second look at the article then says plainly.
            self._context.clear_cookies()
            response = page.goto(HOME, wait_until='domcontentloaded', timeout=_left(deadline))
        except PlaywrightTimeout:
            raise LoginUnreachable('timeout') from None
        except PlaywrightError as error:
            failure = self._why_it_failed(error)
            raise (LoginUnreachable('unreachable') if isinstance(failure, PageDidNotLoad) else failure) from None
        if response is not None and response.status == 403:
            raise Refused('403')
        return self._stopped(self._steps(email, password, deadline))

    def _steps(self, email: str, password: str, deadline: float) -> str:
        """Walk the table in `log_in`, and answer the step it stopped in."""
        page = self._page
        step = self.login_step = 'open'
        try:
            self._answer_cookies(deadline)
            page.locator(LOGIN_BUTTON).first.click(timeout=_left(deadline))
            if self._first_of(deadline, email_field=EMAIL_FIELD) is None or not on_login_service(page.url):
                return step
            step = self.login_step = 'email'
            page.locator(EMAIL_FIELD).fill(email, timeout=_left(deadline))
            page.locator(SUBMIT).first.click(timeout=_left(deadline))
            arrived = self._first_of(deadline, password_field=PASSWORD_FIELD, **_refusals())
            if arrived != 'password_field' or not on_login_service(page.url):
                return step
            step = self.login_step = 'password'
            page.locator(PASSWORD_FIELD).fill(password, timeout=_left(deadline))
            page.locator(SUBMIT).first.click(timeout=_left(deadline))
            step = self.login_step = 'sent'
            if self._first_of(deadline, landed=LANDED, **_refusals()) == 'landed':
                page.wait_for_load_state('load', timeout=_left(deadline))
            return step
        except PlaywrightTimeout:
            return step
        except PlaywrightError as error:
            raise self._why_it_failed(error) from None

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
        """The page the login stopped on. A page mid-navigation has no content yet; wait once.

        A page that died meanwhile answers with no content rather than raising, so the step is
        still reported for what it was.
        """
        for _ in range(2):
            try:
                return LoginEnd(step, self._page.url, self._page.content())
            except PlaywrightError:
                try:
                    self._page.wait_for_timeout(500)
                except PlaywrightError:
                    break
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
