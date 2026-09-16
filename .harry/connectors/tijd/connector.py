"""De Tijd's articles, read as the subscriber reads them, with a login Harry renews by itself.

The news connector reads De Tijd's feed like any other, and hands every article link on
tijd.be here. This opens it in a headed Chromium carrying the saved session and hands back the
page — or, when it cannot, a fixed sentence saying why.

## The rules, in the order they run

1. Open the article with the saved session.
2. A 403 is De Tijd's bot filter. Say so. **Never log in because of one** — a login cannot fix
   it, and the Slack line would send somebody to fix the wrong thing.
3. A page with `paywall-active` needs a login. Log in — unless a login failed recently, in
   which case give the same answer that failure gave.
4. After a login, open the article once more. Still `paywall-active` is the subscription,
   not the login.
5. Save the session after every page read in full, so the cookies De Tijd renews are kept.

## Why this connector says its own faults

Every failure is one Slack line per 24 hours, keyed by the reason's name, raised here rather
than by the news connector. The context that sends it is this connector's, so it scrubs
`EMAIL` and `PASSWORD` — the news connector's would scrub news's secrets, and news has none.
Every sentence is fixed. None carries an exception's text, a URL, the email or the password.

## Why a failed login waits

De Tijd's login service blocks an account after repeated failures. So after a refused
password, a captcha, a login step Harry does not know, or a paywall that outlasted a login,
no new login is tried for 6 hours; every article in that time gets the same answer. A login
page that did not answer at all waits 15 minutes: nothing was refused, so nothing counts
towards a lockout. The wait lives in memory — a restart clears it, and a restart is also how a
corrected password takes effect.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import tempfile
import threading
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from harry.sdk import Context, Registry

from .browser import BrowserFailed, Chromium, LoginUnreachable, PageDidNotLoad, Refused
from .pages import STEPS, login_outcome, paywalled

PAGE_SECONDS = 30.0
"""How long one article page may take to arrive."""

LOGIN_SECONDS = 60.0
"""How long a whole login may take, every step included. A read that logs in first is done
within two pages and a login: about two minutes at the very worst."""

WAIT_AFTER_FAILURE = timedelta(hours=6)
WAIT_AFTER_SILENCE = timedelta(minutes=15)
LOCKOUT_FREE = frozenset({'login-unreachable'})
"""Failures in which nothing was refused, so trying again sooner cannot lock the account."""

STATE_FILE = 'storage-state.json'
LOGGED_IN_AT = 'logged-in-at'

WHY = {
    'refused': (
        'Harry could not log in: De Tijd refused the email or password in '
        '.harry/connectors/tijd/.env.local. Harry waits 6 hours before trying again, or until it restarts'
    ),
    'challenge': (
        'Harry could not log in: the login page asked for a check Harry cannot answer, such as a '
        'captcha. Harry waits 6 hours before trying again'
    ),
    'login-page': (
        'Harry could not log in: at {step}, the login page did not show what Harry expects, so De Tijd '
        'may have changed it. Harry waits 6 hours before trying again'
    ),
    'login-unreachable': "Harry could not log in: De Tijd's homepage did not answer. Harry tries again in 15 minutes",
    'blocked': (
        "De Tijd refused the browser (403). That is De Tijd's bot filter, not the login, so logging "
        'in again will not help'
    ),
    'browser': 'the browser Harry reads De Tijd with could not start, or stopped',
    'timeout': 'the article page did not load within 30 seconds, or could not be reached',
    'page': 'De Tijd answered {status} for the article',
    'paywall': 'Harry logged in, but De Tijd still shows the paywall. Check that the subscription is active',
    'session': ('Harry could not save the De Tijd session in {where}, so every article will need a login until it can'),
}
"""Every sentence this connector can say. Fixed, so there is nothing in one to scrub."""


class Tijd:
    """A logged-in reader for tijd.be, one article at a time."""

    def __init__(
        self,
        email: str,
        password: str,
        session_dir: Path,
        alert: Callable[..., bool],
        log: logging.Logger,
        browser: Callable[[Path | None], Any] = Chromium,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._email = email
        self._password = password
        self._session_dir = session_dir
        self._alert = alert
        self._log = log
        self._browser = browser
        self._now = now
        self._one_at_a_time = threading.Lock()
        self._waiting: tuple[datetime, str, str] | None = None
        """Until when no login is tried, and the reason and sentence every article gets meanwhile."""

    # -- what the news connector calls ---------------------------------------

    def handles(self, link: str) -> bool:
        """Whether a link is De Tijd's to read."""
        host = (urlsplit(link).hostname or '').lower()
        return host == 'tijd.be' or host.endswith('.tijd.be')

    def read(self, link: str) -> dict[str, Any]:
        """`{"url", "html"}` for a page read in full, or `{"why", "said": True}`.

        `said` means the Slack line is already sent, so whoever asked has nothing to report.
        One call at a time: two browsers writing one session file is how it gets corrupted.
        """
        with self._one_at_a_time:
            try:
                with self._browser(self._saved_state()) as browser:
                    return self._read_with(browser, link)
            except Refused:
                return self._fault('blocked')
            except BrowserFailed:
                return self._fault('browser')
            except PageDidNotLoad:
                return self._fault('timeout')

    # -- the rules ------------------------------------------------------------

    def _read_with(self, browser: Any, link: str) -> dict[str, Any]:
        visit = browser.visit(link, PAGE_SECONDS)
        refused = self._refused(visit)
        if refused is not None:
            return refused
        if paywalled(visit.html):
            why = self._log_in(browser)
            if why is not None:
                return self._say(why)
            visit = browser.visit(link, PAGE_SECONDS)
            refused = self._refused(visit)
            if refused is not None:
                return refused
            if paywalled(visit.html):
                return self._say(self._wait('paywall', WHY['paywall']))
        self._save(browser)
        return {'url': visit.url, 'html': visit.html}

    def _refused(self, visit: Any) -> dict[str, Any] | None:
        if visit.status == 403:
            return self._fault('blocked')
        if visit.status is not None and visit.status >= 400:
            return self._fault('page', status=visit.status)
        return None

    def _log_in(self, browser: Any) -> tuple[str, str] | None:
        """None when logged in; otherwise the reason and its sentence, which every article in
        the wait that follows is given too."""
        if self._waiting is not None and self._now() < self._waiting[0]:
            return self._waiting[1], self._waiting[2]
        try:
            end = browser.log_in(self._email, self._password, LOGIN_SECONDS)
        except LoginUnreachable:
            reason, details = 'login-unreachable', {}
        else:
            reason = login_outcome(end)
            details = {'step': STEPS.get(end.step, end.step)}
        if reason is None:
            self._waiting = None
            self._note_the_login()
            self._save(browser)
            return None
        self._log.warning('De Tijd login did not finish: %s', reason)
        return self._wait(reason, WHY[reason].format(**details))

    def _wait(self, reason: str, why: str) -> tuple[str, str]:
        """Hold off the next login, and remember what to say until then."""
        pause = WAIT_AFTER_SILENCE if reason in LOCKOUT_FREE else WAIT_AFTER_FAILURE
        self._waiting = (self._now() + pause, reason, why)
        return reason, why

    # -- the session on disk --------------------------------------------------

    @property
    def _state_path(self) -> Path:
        return self._session_dir / STATE_FILE

    def _saved_state(self) -> Path | None:
        """The session to start from, or None for a first login.

        A file that is not a session — cut off by a full disk, edited by hand — is set aside
        rather than handed to the browser, which would fail on it every call.
        """
        try:
            state = json.loads(self._state_path.read_text(encoding='utf-8'))
        except FileNotFoundError:
            return None
        except (OSError, ValueError):
            self._log.warning('the saved De Tijd session could not be read, so Harry starts without it')
            return None
        if not isinstance(state, dict) or not isinstance(state.get('cookies'), list):
            self._log.warning('the saved De Tijd session is not a browser session, so Harry starts without it')
            return None
        return self._state_path

    def _save(self, browser: Any) -> None:
        """Write the session where only its owner can read it, all at once or not at all."""
        written: str | None = None
        try:
            state = browser.storage_state()
            self._session_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
            handle, written = tempfile.mkstemp(dir=self._session_dir, prefix='.storage-state-', suffix='.tmp')
            with os.fdopen(handle, 'w', encoding='utf-8') as out:
                json.dump(state, out)
            os.chmod(written, 0o600)
            os.replace(written, self._state_path)
            written = None
        except OSError:
            self._fault('session', where=str(self._session_dir))
        except BrowserFailed:
            # The page is already in hand. The session is saved next time instead.
            self._log.warning('the browser closed before the De Tijd session could be saved')
        finally:
            if written is not None:
                with contextlib.suppress(OSError):
                    os.unlink(written)

    def _note_the_login(self) -> None:
        """Log how long the session this login replaced lasted, and remember when this one began."""
        marker = self._session_dir / LOGGED_IN_AT
        now = self._now()
        try:
            began = datetime.fromisoformat(marker.read_text(encoding='utf-8').strip())
        except (OSError, ValueError):
            self._log.info('logged in to De Tijd; no earlier login is recorded here')
        else:
            days = (now - began).total_seconds() / 86400
            self._log.info('logged in to De Tijd; the previous session lasted %.1f days', days)
        try:
            self._session_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
            marker.write_text(now.isoformat(), encoding='utf-8')
        except OSError:
            self._log.warning('could not record when Harry logged in to De Tijd')

    # -- saying so ------------------------------------------------------------

    def _fault(self, reason: str, **details: Any) -> dict[str, Any]:
        return self._say((reason, WHY[reason].format(**details)))

    def _say(self, fault: tuple[str, str]) -> dict[str, Any]:
        reason, why = fault
        self._alert(f'De Tijd: {why}', key=reason)
        self._log.warning('a De Tijd article was not read: %s', reason)
        return {'why': why, 'said': True}


def register(registry: Registry, context: Context) -> None:
    registry.connector(
        Tijd(
            email=str(context.config['email']),
            password=str(context.config['password']),
            session_dir=Path(str(context.config['session_dir'])),
            alert=context.alert,
            log=context.log,
        )
    )
