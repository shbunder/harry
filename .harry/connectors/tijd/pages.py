"""What a De Tijd page says, read by rule from its HTML — never by looking at it and judging.

Two questions, both answered from HTML alone, so a recorded page answers them in a test the
same way a live one does at 06:30.

**Is this article behind the paywall?** De Tijd serves `<html class="paywall-active">` to a
reader it will not give the article to. Measured on 2026-09-16: present in the served HTML for
a reader who is not logged in, absent for a logged-in subscriber. The "Log in" button is no
use as a sign — JavaScript draws it after the page arrives, so a page read early has none
whether or not anybody is logged in.

**How did a login end?** Each step has one expected ending, measured the same day. The
browser reports which step was under way and where it stopped; this names the outcome.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urlsplit

HOME = 'https://www.tijd.be/'
"""Where a login starts. Not the article: there a second dialog, "Dit artikel is alleen voor
abonnees", sits over the Log in button even after the cookie question is answered."""

CONSENT_REFUSE = 'Optionele cookies weigeren'
"""The cookie dialog's button that answers it with the least consent. The dialog covers the
Log in button until it is answered."""

LOGIN_BUTTON = '.trck_sitenav_login:visible'
EMAIL_FIELD = '#username'
PASSWORD_FIELD = '#password'
SUBMIT = 'button[type=submit][name="action"][value="default"]'
"""The same button on both steps of `auth.mediafin.be`. The login page also carries submit
buttons for Apple and Google, which is why the name and value are part of the selector."""

LANDED = re.compile(r'^https://www\.tijd\.be/(?!login-redirect)')
"""Back on De Tijd, and past the page that hands the login over. Measured 2026-09-16: the
password step lands on `www.tijd.be/login-redirect.html`, which navigates on to the homepage
about a second and a half later. Treating the hand-over page as the end sent the next page
load into the middle of that redirect, and Chromium abandoned it."""

REFUSALS = ('error-element-password', 'error-element-username')
"""Where the login service puts "E-mailadres of wachtwoord onjuist" and its relatives."""

CAPTCHA_FRAME = re.compile(r'captcha|challenges|arkoselabs', re.IGNORECASE)

LOGIN_SERVICE = 'auth.mediafin.be'
"""Where De Tijd's login form is, measured 2026-09-16. Nothing is typed anywhere else."""

STEPS = {
    'open': 'opening the login page',
    'email': 'the email step',
    'password': 'the password step',
    'sent': 'after the password was sent',
}
"""The steps a login can stop in, and how each is named to a person. `sent` is everything
after the password was submitted — the only point from which a failure can count towards De
Tijd blocking the account."""


def on_login_service(url: str) -> bool:
    """Whether a page is De Tijd's login service, and so somewhere the email and password may go."""
    return urlsplit(url).hostname == LOGIN_SERVICE


def paywalled(html: str) -> bool:
    """Whether De Tijd withheld the article from whoever this page was served to."""
    return 'paywall-active' in _Elements.of(html).html_classes


@dataclass(frozen=True)
class LoginEnd:
    """Where a login stopped: the step under way, and the page it stopped on."""

    step: str
    url: str
    html: str


def login_outcome(end: LoginEnd) -> str | None:
    """None when the login finished; otherwise the name of what stopped it.

    - finished — the password was sent and the browser is back on www.tijd.be
    - `refused` — the login service put an error on the email or the password
    - `challenge` — the page carries a captcha, which nobody at Harry can answer
    - `login-stalled` — it stopped before the password was sent: a field that did not come in
      time, or a page that was not the login service. Slow or changed, nobody can tell yet, and
      nothing was refused, so it is tried again soon
    - `login-page` — the password was sent and neither ending came: a step the table does not
      have, such as a one-time code. A person has to look

    **A captcha is an element, not a word.** The ordinary login page mentions "captcha" 77
    times in its scripts — recorded 2026-09-16, with no captcha shown — so a page is only a
    challenge when an element carries Auth0's captcha attributes or a frame loads a captcha.
    """
    if end.step == 'sent' and urlsplit(end.url).hostname == 'www.tijd.be':
        return None
    elements = _Elements.of(end.html)
    if any(elements.ids.get(refusal, {}).get('data-error-code') for refusal in REFUSALS):
        return 'refused'
    if elements.captcha:
        return 'challenge'
    if end.step != 'sent':
        return 'login-stalled'
    return 'login-page'


class _Elements(HTMLParser):
    """The few facts these rules read, collected in one pass.

    A parser rather than a regular expression because the text of a `<script>` is not markup:
    `getAttribute("data-captcha-provider")` in the login page's JavaScript is not a captcha.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.html_classes: set[str] = set()
        self.ids: dict[str, dict[str, str]] = {}
        self.captcha = False

    @classmethod
    def of(cls, html: str) -> _Elements:
        parsed = cls()
        parsed.feed(html)
        parsed.close()
        return parsed

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        found = {name: value or '' for name, value in attrs}
        if tag == 'html' and not self.html_classes:
            self.html_classes = set(found.get('class', '').split())
        if found.get('id'):
            self.ids.setdefault(found['id'], found)
        if 'data-captcha-provider' in found or 'data-captcha-sitekey' in found:
            self.captcha = True
        if tag == 'iframe' and CAPTCHA_FRAME.search(found.get('src', '')):
            self.captcha = True
