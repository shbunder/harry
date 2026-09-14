"""The reMarkable tablet, and the one write Harry does to it.

## Why this is so small

The device token is complete read and write over every document on the tablet, with no
scopes. remarkapy offers delete, bulk_delete, move, rename and download; this connector
offers *add a document* and *say what is there*. What Harry can reach and what Harry does
are two different lists, and the gap is the point.

## Why the client is built lazily

`remarkapy.Client.__init__` calls `discover_endpoints()` and then mints a user token — two
network calls, in the constructor. Building it in `register()` would make Harry's start-up
wait on reMarkable's cloud, and a cloud that was down would skip this connector on a morning
when the page only needed somewhere to be written to disk.

## Why the retry is one, and inline

A push either works on the second try or is not going to. A loop would spend the morning
page's build time discovering that, and a background queue would need somewhere to keep the
queue. Two failures raise, so the caller knows, and one line goes to Slack, so a person
knows — those two together are what stop a page quietly not arriving for three weeks.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
from remarkapy import Client, ExpiredToken, RemarkableAPIError

from harry.sdk import Context, Registry

TIMEOUT = 30.0
"""Seconds per call. A page is a few hundred kilobytes and the upload is the slow part;
remarkapy's own default of 20 has been enough in practice, and this is the ceiling for a
call that runs once a morning."""

ATTEMPTS = 2
"""One try, then one retry. Not three: a push that fails twice is a protocol change or a
revoked token, and neither gets better on a third attempt inside the same minute."""

PDF = '.pdf'

PAGE = (509.34, 679.13)
"""Points, width by height — the reMarkable Paper Pro's page, measured in September 2026.

At any other size the tablet rescales what it is given and the type goes soft. The number
lives here because the tablet is the thing that has a page size; anything rendering *for*
the tablet asks the tablet.
"""

MARKDOWN_CSS = (
    """
@page { size: %fpt %fpt; margin: 42pt 36pt; }
body { font-family: Georgia, 'Times New Roman', serif; font-size: 11pt; line-height: 1.45; }
h1 { font-size: 19pt; margin: 0 0 12pt; }
h2 { font-size: 14pt; margin: 18pt 0 6pt; }
h3 { font-size: 12pt; margin: 14pt 0 4pt; }
p, li { orphans: 2; widows: 2; }
code, pre { font-family: 'SF Mono', Menlo, monospace; font-size: 9.5pt; }
pre { white-space: pre-wrap; background: #f4f4f4; padding: 8pt; }
blockquote { margin: 10pt 0 10pt 18pt; font-style: italic; }
table { border-collapse: collapse; } td, th { border: 0.5pt solid #999; padding: 3pt 6pt; }
"""
    % PAGE
)
"""Enough to read a page of prose at arm's length, and nothing more.

This is not the morning page's stylesheet. That page has a front sheet, an outline and a
layout somebody designed; this is "put what I just wrote on the tablet", which wants one
readable column and no decisions.
"""


class Refused(Exception):
    """The tablet would not take it. Carries what to do, never why in protocol terms."""


class Tablet:
    """One folder on one tablet, and the one thing Harry puts in it."""

    def __init__(
        self,
        token: str,
        folder: str,
        log: logging.Logger,
        alert: Callable[..., bool],
        connect: Callable[[str], Any] | None = None,
    ) -> None:
        self._token = token
        self.folder = folder
        self._log = log
        self._alert = alert
        self._connect = connect or _reach_remarkable
        self._client: Any | None = None
        self._folder_id: str | None = None

    # -- what the digest calls ------------------------------------------------

    def push(self, path: str | Path, name: str) -> dict:
        """Put a PDF on the tablet under `name`. The signature the morning page was built for.

        Raises rather than returning a failure shape: a page that did not arrive is not
        information the caller can use, it is a thing that did not happen.
        """
        document = Path(path)
        if document.suffix.lower() != PDF:
            raise Refused(f'{document.name} is not a PDF, and the tablet only takes PDFs from here')
        if not document.is_file():
            raise Refused(f'there is no file at {document}')
        return self.push_bytes(document.read_bytes(), name)

    def push_bytes(self, payload: bytes, name: str) -> dict:
        """The same push, for something that was rendered rather than read off disk."""
        entry = self._trying(f'push {name!r}', lambda client: client.put_pdf(name, payload, parent=self._where(client)))
        return {'where': self.folder, 'id': entry.id, 'name': name}

    # -- what the tools call --------------------------------------------------

    def push_markdown(self, markdown: str, name: str) -> dict:
        """Render markdown to a page the tablet will not rescale, then push it."""
        return self.push_bytes(render_markdown(markdown, name), name)

    def documents(self) -> list[dict]:
        """What is already in the folder, newest first.

        A folder nobody has created yet is empty rather than an error: it is the true answer,
        and the first push will make it.
        """
        found = self._trying('list the folder', self._read_folder)
        return sorted(found, key=lambda item: item['modified'] or '', reverse=True)

    def _read_folder(self, client: Any) -> list[dict]:
        where = self._find_folder(client)
        if where is None:
            return []
        return [
            {'id': entry.id, 'name': entry.visibleName, 'modified': getattr(entry, 'lastModified', None)}
            for entry in client.list_directory_hydrated(where)
            if entry.type == 'DocumentType'
        ]

    # -- the work -------------------------------------------------------------

    def _trying(self, what: str, call: Callable[[Any], Any]) -> Any:
        """One attempt, then one more, then say so to the caller and to a person.

        A revoked token is not retried. It will be refused exactly as fast the second time,
        and the sentence a person needs is different — there is something to *do* about it.
        """
        last: Exception | None = None
        for attempt in range(1, ATTEMPTS + 1):
            try:
                return call(self._reach())
            except ExpiredToken as error:
                self._give_up('the tablet refused the token — pair this machine again with make remarkable-pair')
                raise Refused(
                    'the tablet refused the token — pair this machine again with make remarkable-pair'
                ) from error
            except (RemarkableAPIError, httpx.HTTPError, OSError) as error:
                last = error
                self._client = self._folder_id = None
                self._log.warning('could not %s (attempt %d of %d)', what, attempt, ATTEMPTS)

        why = _why(last)
        self._give_up(why)
        raise Refused(f'could not {what}: {why}') from last

    def _give_up(self, why: str) -> None:
        """One line, once a day, naming the tablet. Never the token, never the response."""
        self._alert(f'reMarkable: {why}', key='push')

    def _reach(self) -> Any:
        """The client, built on first use rather than at start-up."""
        if self._client is None:
            self._client = self._connect(self._token)
        return self._client

    def _where(self, client: Any) -> str:
        """The folder's id, making it the first time and remembering it after."""
        if self._folder_id is None:
            found = self._find_folder(client)
            self._folder_id = found if found is not None else client.put_folder(self.folder).id
            self._log.info('documents go into %r on the tablet', self.folder)
        return self._folder_id

    def _find_folder(self, client: Any) -> str | None:
        """The top-level folder by name, or None. Name rather than id, because a person
        configured it and a person reads it off the tablet."""
        for item in client.list_directory(''):
            if item.type == 'CollectionType' and item.visibleName == self.folder:
                return item.id
        return None


def render_markdown(markdown: str, title: str) -> bytes:
    """Markdown to a PDF at the tablet's exact page size.

    Imported here rather than at module scope: WeasyPrint pulls in a font stack and takes
    about a second to import, and most of Harry's runs never render anything.
    """
    from weasyprint import HTML

    document = f'<title>{_plain(title)}</title><style>{MARKDOWN_CSS}</style>{to_html(markdown)}'
    return HTML(string=document).write_pdf()


def to_html(markdown: str) -> str:
    """Markdown to the HTML that gets rendered.

    `html: False` is the whole security posture of this function: raw HTML inside the
    markdown is shown as text rather than interpreted, so a document Claude was asked to
    forward cannot bring markup of its own into the page.
    """
    from markdown_it import MarkdownIt

    return MarkdownIt('commonmark', {'html': False}).enable('table').render(markdown)


def _plain(text: str) -> str:
    """For the one place a caller's string lands inside markup. `html: False` above keeps
    the markdown itself inert; the title does not go through that renderer."""
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def _reach_remarkable(token: str) -> Client:
    """A remarkapy client that touches nothing outside this process.

    `persist_config` stays off — the default would write the token into `~/.rmapi`, and the
    one place this token lives is the `.env.local` a person put it in. `interactive` stays
    off because there is nobody at the keyboard at 06:30.
    """
    return Client(device_token=token, timeout=TIMEOUT, interactive=False, persist_config=False)


def _why(error: Exception | None) -> str:
    """What to tell somebody, from what went wrong. No traceback, no URL, no response body.

    This sentence goes to Slack. remarkapy's errors quote the request back, and the request
    carried the device token.
    """
    if isinstance(error, httpx.TimeoutException):
        return f'the tablet did not answer within {TIMEOUT:g}s'
    if isinstance(error, httpx.HTTPError | OSError):
        return 'the tablet could not be reached'
    return 'the tablet rejected the request — if every write is failing, reMarkable changed the protocol'


def register(registry: Registry, context: Context) -> None:
    registry.connector(
        Tablet(
            token=str(context.config['device_token']),
            folder=str(context.config['folder']),
            log=context.log,
            alert=context.alert,
        )
    )
