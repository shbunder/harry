"""The tablet: one folder, one write, and what happens when it will not take it.

Loaded, not imported — `pyproject.toml` keeps `.harry` off pytest's path, so these copy the
real folder into a temporary root and run it through `load()`.

**No test here reaches reMarkable's cloud** except the one marked `live`, which pushes a real
page to a real tablet and is never part of the gate. The rest swap the connector's own
`connect` seam for a stand-in — the same object production builds, with the client it would
have dialled replaced. `test_the_stand_in_has_the_same_shape_as_the_real_client` is what
stops that stand-in drifting away from remarkapy.
"""

from __future__ import annotations

import inspect
import json
import logging
from dataclasses import dataclass
from pathlib import Path

import httpx
import pytest
from remarkapy import Client, ExpiredToken, RemarkableAPIError

from harry.alerts import Alerts
from harry.loader import load

from .capability_copy import copy_capability

REPO = Path(__file__).parent.parent
TOKEN = 'device-token-that-must-never-be-printed-0f2744'
"""Planted, and distinctive, so a test can assert it appears nowhere."""


class Somewhere:
    def __init__(self) -> None:
        self.heard: list[str] = []

    def __call__(self, message: str) -> None:
        self.heard.append(message)


@dataclass
class Item:
    """What remarkapy hands back from a listing."""

    id: str
    hash: str = 'h'
    type: str = 'DocumentType'
    visibleName: str = 'a document'  # noqa: N815 — remarkapy's spelling, and it is the wire's
    parent: str = ''
    lastModified: str = '1789384626339'  # noqa: N815 — same, and epoch milliseconds, as recorded


class StandIn:
    """remarkapy's client, with the network taken out.

    Only the four calls this connector makes. Everything else remarkapy offers — delete,
    move, rename, download — is absent on purpose: if the connector grows a fifth call, this
    stand-in fails rather than quietly allowing it.
    """

    def __init__(self, folders: list[Item] | None = None, documents: list[Item] | None = None) -> None:
        self.folders = folders if folders is not None else []
        self.documents = documents if documents is not None else []
        self.pushed: list[tuple[str, bytes, str]] = []
        self.folders_made = 0
        self.fail_for = 0
        self.fails_with: Exception = RemarkableAPIError('nope')

    def _maybe_fail(self) -> None:
        if self.fail_for > 0:
            self.fail_for -= 1
            raise self.fails_with

    def list_directory(self, directory_ref: str = '', refresh: bool = False) -> list[Item]:
        self._maybe_fail()
        return [*self.folders, *(d for d in self.documents if d.parent == directory_ref)]

    def list_directory_hydrated(self, directory_ref: str = '', refresh: bool = False) -> list[Item]:
        self._maybe_fail()
        return [d for d in self.documents if d.parent == directory_ref]

    def put_folder(self, visible_name: str, *, parent: str = '', refresh: bool = False) -> Item:
        self._maybe_fail()
        self.folders_made += 1
        made = Item(id=f'folder-{self.folders_made}', type='CollectionType', visibleName=visible_name, parent=parent)
        self.folders.append(made)
        return made

    def put_pdf(self, visible_name: str, payload: bytes, *, parent: str = '', refresh: bool = False) -> Item:
        self._maybe_fail()
        self.pushed.append((visible_name, payload, parent))
        made = Item(id=f'doc-{len(self.pushed)}', visibleName=visible_name, parent=parent)
        self.documents.append(made)
        return made


@pytest.fixture
def tablet(tmp_path, monkeypatch):
    """The real `.harry/connectors/remarkable/`, loaded, with a stand-in for the cloud."""
    for key in ('DEVICE_TOKEN', 'FOLDER'):
        monkeypatch.delenv(f'HARRY_REMARKABLE_{key}', raising=False)

    def build(*, settings: str = f'DEVICE_TOKEN={TOKEN}\n', cloud: StandIn | None = None, tools: tuple[str, ...] = ()):
        root = tmp_path / 'root'
        for where in ('connectors/remarkable', *(f'tools/{tool}' for tool in tools)):
            (root / where).parent.mkdir(parents=True, exist_ok=True)
            copy_capability(REPO / '.harry' / where, root / where)
        (root / 'connectors' / 'remarkable' / '.env.local').write_text(settings, encoding='utf-8')

        alerts = Alerts()
        catalogue = load([root], alerts=alerts)
        alerts.attach(catalogue)
        sink = Somewhere()
        alerts._sinks = [sink]  # noqa: SLF001 — no Slack connector in this root to take them

        found = catalogue.get('connector', 'remarkable')
        if found is not None and found.target is not None:
            # The client is built on first use, so nothing has dialled out yet. This is the
            # same object production made — only what it reaches is different.
            standing_in = cloud if cloud is not None else StandIn()
            found.target._connect = lambda token: standing_in  # noqa: SLF001
        return catalogue, sink

    return build


def connector(built):
    catalogue, _ = built
    found = catalogue.get('connector', 'remarkable')
    assert found is not None and found.target is not None, [f'{c.name}: {c.reason}' for c in catalogue.skipped]
    return found.target


def a_pdf(where: Path) -> Path:
    where.write_bytes(b'%PDF-1.7\n% not a real one, and nothing here parses it\n')
    return where


# ---------------------------------------------------------------------------
# One folder, one write
# ---------------------------------------------------------------------------


def test_a_pdf_is_uploaded_under_the_name_it_was_given(tablet, tmp_path):
    cloud = StandIn()
    where = connector(tablet(cloud=cloud)).push(a_pdf(tmp_path / 'page.pdf'), 'Morning page — Monday 14 September')

    assert len(cloud.pushed) == 1
    name, payload, parent = cloud.pushed[0]
    assert name == 'Morning page — Monday 14 September', 'the visible name is what a person reads on the tablet'
    assert payload.startswith(b'%PDF')
    assert parent == 'folder-1', 'it went inside the folder, not to the top level'
    assert where == {'where': 'Harry', 'id': 'doc-1', 'name': 'Morning page — Monday 14 September'}


def test_the_folder_is_made_once_and_found_after(tablet, tmp_path):
    """Two pushes on one morning must not leave two folders called Harry."""
    cloud = StandIn()
    tablet_client = connector(tablet(cloud=cloud))

    tablet_client.push(a_pdf(tmp_path / 'one.pdf'), 'One')
    tablet_client.push(a_pdf(tmp_path / 'two.pdf'), 'Two')

    assert cloud.folders_made == 1
    assert [name for name, _, _ in cloud.pushed] == ['One', 'Two']


def test_an_existing_folder_is_used_rather_than_a_second_one(tablet, tmp_path):
    cloud = StandIn(folders=[Item(id='already-there', type='CollectionType', visibleName='Harry')])

    connector(tablet(cloud=cloud)).push(a_pdf(tmp_path / 'page.pdf'), 'A page')

    assert cloud.folders_made == 0
    assert cloud.pushed[0][2] == 'already-there'


def test_a_different_folder_is_a_setting(tablet, tmp_path):
    cloud = StandIn()
    built = tablet(settings=f'DEVICE_TOKEN={TOKEN}\nFOLDER=Reading\n', cloud=cloud)

    answer = connector(built).push(a_pdf(tmp_path / 'page.pdf'), 'A page')

    assert answer['where'] == 'Reading'
    assert cloud.folders[0].visibleName == 'Reading'


def test_something_that_is_not_a_pdf_is_refused_before_anything_is_uploaded(tablet, tmp_path):
    cloud = StandIn()
    not_a_pdf = tmp_path / 'notes.txt'
    not_a_pdf.write_text('hello', encoding='utf-8')

    with pytest.raises(Exception, match='not a PDF'):
        connector(tablet(cloud=cloud)).push(not_a_pdf, 'Notes')

    assert cloud.pushed == []


def test_a_file_that_is_not_there_is_refused(tablet, tmp_path):
    cloud = StandIn()

    with pytest.raises(Exception, match='there is no file at'):
        connector(tablet(cloud=cloud)).push(tmp_path / 'gone.pdf', 'Gone')

    assert cloud.pushed == []


# ---------------------------------------------------------------------------
# What is already there
# ---------------------------------------------------------------------------


def test_documents_come_back_newest_first(tablet):
    cloud = StandIn(
        folders=[Item(id='f', type='CollectionType', visibleName='Harry')],
        documents=[
            Item(id='old', visibleName='Friday', parent='f', lastModified='1789124400000'),
            Item(id='new', visibleName='Monday', parent='f', lastModified='1789384626339'),
        ],
    )

    found = connector(tablet(cloud=cloud)).documents()

    assert [item['name'] for item in found] == ['Monday', 'Friday']
    assert found[0] == {'id': 'new', 'name': 'Monday', 'modified': '2026-09-14T11:17:06.339000Z'}


def test_a_recorded_listing_becomes_a_time_a_person_can_read(tablet):
    """reMarkable sends epoch milliseconds in a string. `"1789384626339"` sorts correctly by
    luck and tells a reader nothing, and it is the field `remarkable_list_documents` shows
    Claude — so the conversion is the difference between a true answer and a shaped one.

    Built from a real listing rather than from what a stand-in was guessed to return, which
    is exactly the mistake this fixture was recorded to catch.
    """
    recorded = json.loads((REPO / 'tests' / 'fixtures' / 'remarkable' / 'folder-listing.json').read_text('utf-8'))
    cloud = StandIn(
        folders=[Item(id='12c9c3b8-6108-4f3b-abcd-06736f99e65e', type='CollectionType', visibleName='Harry')],
        documents=[
            Item(**{key: entry[key] for key in ('id', 'hash', 'type', 'visibleName', 'lastModified', 'parent')})
            for entry in recorded
        ],
    )

    found = connector(tablet(cloud=cloud)).documents()

    assert [item['modified'] for item in found] == ['2026-09-14T11:17:06.339000Z', '2026-09-14T11:10:42.902000Z']
    assert all(item['name'] == 'Harry says hello — from make test-live' for item in found)


def test_a_timestamp_in_a_shape_nobody_expected_is_passed_through(tablet):
    """If reMarkable ever starts sending ISO, the listing must not start returning None."""
    cloud = StandIn(
        folders=[Item(id='f', type='CollectionType', visibleName='Harry')],
        documents=[Item(id='d', visibleName='Monday', parent='f', lastModified='2026-09-14T06:30:00Z')],
    )

    assert connector(tablet(cloud=cloud)).documents()[0]['modified'] == '2026-09-14T06:30:00Z'


def test_a_folder_nobody_has_made_yet_lists_empty(tablet):
    """The true answer, and the first push will make it. An error here would read as a
    broken tablet on a morning when nothing is wrong."""
    assert connector(tablet(cloud=StandIn())).documents() == []


def test_a_folder_of_folders_lists_only_documents(tablet):
    cloud = StandIn(
        folders=[Item(id='f', type='CollectionType', visibleName='Harry')],
        documents=[
            Item(id='doc', visibleName='Monday', parent='f'),
            Item(id='sub', type='CollectionType', visibleName='Archive', parent='f'),
        ],
    )

    assert [item['name'] for item in connector(tablet(cloud=cloud)).documents()] == ['Monday']


# ---------------------------------------------------------------------------
# One retry, then say so
# ---------------------------------------------------------------------------


def test_one_failure_is_retried_and_the_retry_is_the_answer(tablet, tmp_path, caplog):
    cloud = StandIn()
    cloud.fail_for = 1
    built = tablet(cloud=cloud)

    with caplog.at_level(logging.WARNING, logger='harry.capability.remarkable'):
        answer = connector(built).push(a_pdf(tmp_path / 'page.pdf'), 'A page')

    assert answer['id'] == 'doc-1'
    assert 'attempt 1 of 2' in caplog.text
    _, sink = built
    assert sink.heard == [], 'a retry that worked is not a fault'


def test_two_failures_raise_and_put_one_line_in_slack(tablet, tmp_path):
    cloud = StandIn()
    cloud.fail_for = 99
    built = tablet(cloud=cloud)

    with pytest.raises(Exception, match='could not push'):
        connector(built).push(a_pdf(tmp_path / 'page.pdf'), 'A page')

    _, sink = built
    assert sink.heard == [
        'reMarkable: the tablet rejected the request — if every write is failing, reMarkable changed the protocol'
    ]


def test_exactly_two_attempts_are_made(tablet, tmp_path):
    """Not three. A push that failed twice is a protocol change or a revoked token, and
    neither improves inside the same minute — while the morning page is still building."""
    calls: list[str] = []

    class Counting(StandIn):
        def list_directory(self, directory_ref: str = '', refresh: bool = False):
            calls.append('list')
            raise httpx.ConnectError('no route to host')

    with pytest.raises(Exception, match='could not push'):
        connector(tablet(cloud=Counting())).push(a_pdf(tmp_path / 'page.pdf'), 'A page')

    assert len(calls) == 2


@pytest.mark.parametrize(
    ('failure', 'why'),
    [
        (httpx.ConnectError('no route to host'), 'the tablet could not be reached'),
        (httpx.ReadTimeout('too slow'), 'the tablet did not answer within 30s'),
        (OSError('the socket went away'), 'the tablet could not be reached'),
        (
            RemarkableAPIError('400'),
            'the tablet rejected the request — if every write is failing, reMarkable changed the protocol',
        ),
    ],
)
def test_each_kind_of_failure_says_what_it_was(tablet, tmp_path, failure, why):
    cloud = StandIn()
    cloud.fail_for = 99
    cloud.fails_with = failure
    built = tablet(cloud=cloud)

    with pytest.raises(Exception, match='could not push'):
        connector(built).push(a_pdf(tmp_path / 'page.pdf'), 'A page')

    _, sink = built
    assert sink.heard == [f'reMarkable: {why}']


def test_a_revoked_token_says_to_pair_again_and_is_not_retried(tablet, tmp_path):
    """It will be refused exactly as fast the second time, and there is something a person
    can actually do about this one."""
    attempts: list[str] = []

    class Revoked(StandIn):
        def list_directory(self, directory_ref: str = '', refresh: bool = False):
            attempts.append('tried')
            raise ExpiredToken('device token rejected')

    built = tablet(cloud=Revoked())

    with pytest.raises(Exception, match='pair this machine again'):
        connector(built).push(a_pdf(tmp_path / 'page.pdf'), 'A page')

    assert len(attempts) == 1, 'a revoked token is not retried'
    _, sink = built
    assert sink.heard == [
        'reMarkable: the tablet refused the token — pair this machine again with make remarkable-pair'
    ]


def test_a_failed_listing_does_not_silence_the_next_failed_push(tablet, tmp_path):
    """An alert is said once per key per day. One key for the whole connector would let a
    listing — which Claude can ask for at any hour — spend the day's budget, and the 06:30
    push would then fail in silence. That is the three-week silence this connector exists to
    prevent, arriving through the thing meant to prevent it.
    """
    cloud = StandIn()
    cloud.fail_for = 99
    built = tablet(cloud=cloud)
    client = connector(built)

    with pytest.raises(Exception, match='could not list'):
        client.documents()
    with pytest.raises(Exception, match='could not push'):
        client.push(a_pdf(tmp_path / 'page.pdf'), 'A page')

    _, sink = built
    assert len(sink.heard) == 2, "the listing swallowed the push's alert"


def test_a_failed_listing_does_not_silence_a_revoked_token(tablet, tmp_path):
    """The worst version of the same bug: a transient connection failure at 07:00 hiding the
    one message that says there is something to do about it."""

    class Revoked(StandIn):
        def list_directory(self, directory_ref: str = '', refresh: bool = False):
            if self.fail_for > 0:
                self.fail_for -= 1
                raise httpx.ConnectError('no route to host')
            raise ExpiredToken('device token rejected')

    cloud = Revoked()
    cloud.fail_for = 2
    built = tablet(cloud=cloud)
    client = connector(built)

    with pytest.raises(Exception, match='could not list'):
        client.documents()
    with pytest.raises(Exception, match='pair this machine again'):
        client.push(a_pdf(tmp_path / 'page.pdf'), 'A page')

    _, sink = built
    assert any('pair this machine again' in line for line in sink.heard), sink.heard


def test_a_failure_that_keeps_failing_says_so_once_a_day(tablet, tmp_path):
    cloud = StandIn()
    cloud.fail_for = 99
    built = tablet(cloud=cloud)
    client = connector(built)

    for _ in range(3):
        with pytest.raises(Exception, match='could not push'):
            client.push(a_pdf(tmp_path / 'page.pdf'), 'A page')

    _, sink = built
    assert len(sink.heard) == 1, 'keyed on the push, so a tablet down all week is one line a day'


# ---------------------------------------------------------------------------
# The credential
# ---------------------------------------------------------------------------


def test_the_device_token_reaches_no_log_no_error_and_no_slack(tablet, tmp_path, caplog):
    """Complete read and write over every document on the tablet, with no scopes. It goes
    in a gitignored file and comes out nowhere."""
    cloud = StandIn()
    cloud.fail_for = 99
    cloud.fails_with = RemarkableAPIError(f'rejected request with Authorization: Bearer {TOKEN}')
    built = tablet(cloud=cloud)

    with caplog.at_level(logging.DEBUG), pytest.raises(Exception) as refused:
        connector(built).push(a_pdf(tmp_path / 'page.pdf'), 'A page')

    _, sink = built
    assert TOKEN not in caplog.text, 'the token reached the log'
    assert TOKEN not in str(refused.value), 'the token reached the error the caller sees'
    assert TOKEN not in ' '.join(sink.heard), 'the token reached Slack'


def test_no_token_skips_the_connector_and_says_which_setting(tablet):
    catalogue, _ = tablet(settings='FOLDER=Harry\n')

    found = catalogue.get('connector', 'remarkable')
    assert found is not None and found.target is None
    assert found.reason == 'required setting device_token is not set'


def test_nothing_is_dialled_until_something_is_pushed(tablet):
    """remarkapy's constructor makes two network calls. Building the client at start-up
    would make Harry's boot wait on reMarkable's cloud, and a cloud that was down would
    cost the connector on a morning the page only needed to be written to disk."""
    reached: list[str] = []

    def refuse(token):
        reached.append(token)
        raise AssertionError('the client was built before anything asked for it')

    catalogue, _ = tablet()
    found = catalogue.get('connector', 'remarkable')
    assert found is not None and found.target is not None
    found.target._connect = refuse  # noqa: SLF001

    assert reached == [], 'loading the connector dialled out'


# ---------------------------------------------------------------------------
# The stand-in, and the pin
# ---------------------------------------------------------------------------


def test_the_stand_in_has_the_same_shape_as_the_real_client():
    """Every test above talks to `StandIn`. This is what stops it drifting from remarkapy:
    each method it offers must exist on the real client, with the same parameters."""
    for name in ('list_directory', 'list_directory_hydrated', 'put_folder', 'put_pdf'):
        theirs = inspect.signature(getattr(Client, name))
        ours = inspect.signature(getattr(StandIn, name))
        assert list(ours.parameters) == list(theirs.parameters), f'{name} has drifted from remarkapy'


def test_the_connector_only_ever_asks_for_four_things():
    """The token permits delete, move and rename. The connector does not, and the stand-in
    is the thing that fails if one appears."""
    source = (REPO / '.harry' / 'connectors' / 'remarkable' / 'connector.py').read_text(encoding='utf-8')

    for forbidden in ('delete', 'bulk_move', 'rename', 'download_item'):
        assert f'client.{forbidden}' not in source, f'{forbidden} is not something Harry does to your tablet'


def test_remarkapy_is_pinned_exactly_and_says_why():
    """A range would deliver the release that broke every write, on the next rebuild, on a
    morning nobody changed anything."""
    declared = (REPO / 'pyproject.toml').read_text(encoding='utf-8')

    assert '"remarkapy==0.3.1"' in declared
    assert 'broke every write in August 2026' in declared


def test_the_image_does_not_carry_a_second_client_for_the_tablet():
    """Two reverse-engineered protocol implementations would be two things to keep working
    and twice the surface holding a token that can rewrite every document on the device.

    This reads the Dockerfile rather than pyproject.toml, because that is where the binary
    actually was — downloaded from GitHub at build time for a call nothing made.
    """
    image = (REPO / 'Dockerfile').read_text(encoding='utf-8')
    instructions = [line for line in image.splitlines() if line.strip() and not line.lstrip().startswith('#')]

    assert not [line for line in instructions if 'rmapi' in line], 'the Go rmapi binary is back in the image'
    assert not [line for line in instructions if 'curl' in line], 'curl was only there to fetch rmapi'


def test_the_connector_imports_the_sdk_and_nothing_else():
    from harry.boundary import forbidden_imports

    assert forbidden_imports(REPO / '.harry' / 'connectors' / 'remarkable') == []


# ---------------------------------------------------------------------------
# Markdown, rendered for this device and no other
# ---------------------------------------------------------------------------

POINTS_PER_PIXEL = 72 / 96
"""WeasyPrint reports a page in CSS pixels. The tablet's page is quoted in points, which is
what `@page size` is written in, so one of the two has to be converted to compare them."""


def rendered_document(tablet, markdown: str, title: str) -> str:
    """The HTML `render_markdown` actually hands WeasyPrint.

    Rendering a document the test built itself would prove the stylesheet constant is right
    and nothing about whether the function uses it. Delete the `<style>` from
    `render_markdown` and the render silently falls back to A4 — measured, 595.28 by 841.89
    points — with the tablet rescaling every page and the type going soft.
    """
    import weasyprint

    module = _connector_module(tablet)
    handed: list[str] = []

    class Capturing:
        def __init__(self, string: str) -> None:
            handed.append(string)

        def write_pdf(self) -> bytes:
            return b'%PDF-1.7 not rendered'

    original = weasyprint.HTML
    try:
        weasyprint.HTML = Capturing  # type: ignore[assignment] — put back in the finally
        module['render_markdown'](markdown, title)
    finally:
        weasyprint.HTML = original
    assert len(handed) == 1
    return handed[0]


def test_markdown_is_rendered_at_the_page_the_tablet_will_not_rescale(tablet):
    """509.34 by 679.13 points, measured against a Paper Pro. At any other size the tablet
    rescales what it is given and the type goes soft.

    Rendered from the document `render_markdown` produced, not from one this test wrote, so
    the stylesheet going missing is a red test rather than a soft page.
    """
    from weasyprint import HTML

    page = HTML(string=rendered_document(tablet, '# A page\n\nSome prose.', 'A page')).render().pages[0]

    assert round(page.width * POINTS_PER_PIXEL, 2) == 509.34
    assert round(page.height * POINTS_PER_PIXEL, 2) == 679.13


def test_markdown_becomes_a_real_pdf_with_the_prose_in_it(tablet):
    render = _connector_module(tablet)['render_markdown']

    payload = render('# A heading\n\nSome **prose**.\n\n- one\n- two\n', 'A heading')

    assert payload.startswith(b'%PDF'), 'not a PDF'
    assert len(payload) > 1000


def test_a_title_with_markup_in_it_cannot_reach_the_document_as_markup(tablet):
    """The title is the one caller string that lands inside markup — the markdown itself is
    rendered with HTML turned off, and the title does not go through that renderer.

    A title of `</title><style>@page{size:A4}</style>` would otherwise replace the page
    size, which is the one thing about this document that has to be right.
    """
    escaping = '</title><style>@page{size:A4}</style>'

    document = rendered_document(tablet, 'hello', escaping)

    assert escaping not in document, 'the title reached the document as markup'
    assert '&lt;/title&gt;' in document
    assert 'size: 509.340000pt' in document, 'the injected page size won'


def test_html_inside_the_markdown_is_shown_rather_than_run(tablet):
    """A document Claude was asked to forward cannot bring markup of its own into the page.
    Turn `html` back on in the connector and this goes red."""
    to_html = _connector_module(tablet)['to_html']

    built = to_html('Before\n\n<script>alert(1)</script>\n\nAfter')

    assert '&lt;script&gt;' in built
    assert '<script>' not in built


def test_a_table_in_the_markdown_becomes_a_table(tablet):
    """CommonMark has no tables; the connector enables them, and a page of notes with a
    table in it is a normal thing to send."""
    to_html = _connector_module(tablet)['to_html']

    assert '<table>' in to_html('| a | b |\n|---|---|\n| 1 | 2 |\n')


def _connector_module(tablet) -> dict:
    """The connector's own module namespace, reached through the object the loader built.

    `.harry` is off pytest's path on purpose, so there is no import for it — this goes
    through a method of the instance production made.
    """
    return connector(tablet(cloud=StandIn())).push_markdown.__func__.__globals__


# ---------------------------------------------------------------------------
# The two tools, the way Claude reaches them
# ---------------------------------------------------------------------------

BOTH_TOOLS = ('remarkable_push_document', 'remarkable_list_documents')


async def through_mcp(built, tmp_path, name: str, arguments: dict | None = None, raise_on_error: bool = True):
    """Find the tool the way a session does, then call it."""
    from fastmcp import Client

    from harry.mcp import FIND_TOOLS, build_server
    from harry.store import Store

    catalogue, _ = built
    async with Client(build_server(catalogue, Store(tmp_path / 'jobs.json'))) as connected:
        await connected.call_tool(FIND_TOOLS, {'query': 'remarkable'})
        return await connected.call_tool(name, arguments or {}, raise_on_error=raise_on_error)


async def test_both_tools_defer_and_are_found_by_search(tablet, tmp_path):
    from fastmcp import Client

    from harry.mcp import FIND_TOOLS, build_server
    from harry.store import Store

    catalogue, _ = tablet(tools=BOTH_TOOLS)

    async with Client(build_server(catalogue, Store(tmp_path / 'jobs.json'))) as connected:
        loaded = [tool.name for tool in await connected.list_tools()]
        assert not set(BOTH_TOOLS) & set(loaded), 'both should defer'

        found = (await connected.call_tool(FIND_TOOLS, {'query': 'remarkable'})).data
        assert sorted(row['name'] for row in found['found']) == sorted(BOTH_TOOLS)


async def test_the_push_tool_says_it_writes_and_that_it_does_not_destroy(tablet, tmp_path):
    """This is how a client can gate the tool that reaches your tablet without gating the
    one that only looks."""
    from fastmcp import Client

    from harry.mcp import FIND_TOOLS, build_server
    from harry.store import Store

    catalogue, _ = tablet(tools=BOTH_TOOLS)

    async with Client(build_server(catalogue, Store(tmp_path / 'jobs.json'))) as connected:
        await connected.call_tool(FIND_TOOLS, {'query': 'remarkable'})
        published = {tool.name: tool for tool in await connected.list_tools()}

    push = published['remarkable_push_document'].annotations
    listing = published['remarkable_list_documents'].annotations
    assert push is not None and listing is not None
    assert push.read_only_hint is False and push.destructive_hint is False, 'it adds; adding is not destroying'
    assert listing.read_only_hint is True


async def test_claude_can_push_a_pdf_it_has_a_path_to(tablet, tmp_path):
    cloud = StandIn()
    built = tablet(cloud=cloud, tools=BOTH_TOOLS)
    page = a_pdf(tmp_path / 'page.pdf')

    answer = await through_mcp(built, tmp_path, 'remarkable_push_document', {'path': str(page), 'name': 'A page'})

    assert answer.data == {'where': 'Harry', 'id': 'doc-1', 'name': 'A page'}
    assert cloud.pushed[0][0] == 'A page'


async def test_claude_can_push_markdown_it_just_wrote(tablet, tmp_path):
    """The useful version of this tool. One that only took a path could only be called by
    something that had already written a file."""
    cloud = StandIn()
    built = tablet(cloud=cloud, tools=BOTH_TOOLS)

    answer = await through_mcp(
        built, tmp_path, 'remarkable_push_document', {'markdown': '# Notes\n\nSome prose.', 'name': 'Notes'}
    )

    assert answer.data['name'] == 'Notes'
    assert cloud.pushed[0][1].startswith(b'%PDF'), 'the markdown was not rendered'


@pytest.mark.parametrize(
    ('arguments', 'why'),
    [
        ({'name': 'A page'}, 'pass path'),
        ({'name': 'A page', 'path': '/tmp/x.pdf', 'markdown': '# x'}, 'not both'),
    ],
)
async def test_neither_or_both_is_an_error_saying_which(tablet, tmp_path, arguments, why):
    built = tablet(cloud=StandIn(), tools=BOTH_TOOLS)

    result = await through_mcp(built, tmp_path, 'remarkable_push_document', arguments, raise_on_error=False)

    assert result.is_error is True
    assert why in str(result.content[0].text)  # type: ignore[union-attr] — an error is one TextContent


async def test_claude_can_see_what_is_already_on_the_tablet(tablet, tmp_path):
    cloud = StandIn(
        folders=[Item(id='f', type='CollectionType', visibleName='Harry')],
        documents=[
            Item(id='old', visibleName='Friday', parent='f', lastModified='2026-09-11T06:30:00Z'),
            Item(id='new', visibleName='Monday', parent='f', lastModified='2026-09-14T06:30:00Z'),
        ],
    )
    built = tablet(cloud=cloud, tools=BOTH_TOOLS)

    answer = await through_mcp(built, tmp_path, 'remarkable_list_documents')

    assert [item['name'] for item in answer.data] == ['Monday', 'Friday']


def test_both_tools_are_skipped_when_there_is_no_token(tablet):
    catalogue, _ = tablet(settings='FOLDER=Harry\n', tools=BOTH_TOOLS)

    for name in BOTH_TOOLS:
        found = catalogue.get('tool', name)
        assert found is not None and found.target is None, f'{name} loaded without a connector'
        assert found.reason == 'needs remarkable, which did not load'


def test_the_connector_lists_both_tools_in_provides():
    """Exposure is the connector's choice. The token also permits delete, move and rename,
    and none of those is listed here — which is the point of the list."""
    declaration = (REPO / '.harry' / 'connectors' / 'remarkable' / 'CONNECTOR.md').read_text(encoding='utf-8')

    assert 'provides: [remarkable_push_document, remarkable_list_documents]' in declaration


def test_both_tools_import_the_sdk_and_nothing_else():
    from harry.boundary import forbidden_imports

    for name in BOTH_TOOLS:
        assert forbidden_imports(REPO / '.harry' / 'tools' / name) == []


# ---------------------------------------------------------------------------
# The tablet itself, which no stand-in can vouch for
# ---------------------------------------------------------------------------


@pytest.mark.live
def test_a_real_page_reaches_a_real_tablet():
    """The only thing the stand-in cannot prove: that the protocol still works.

    Everything above asserts what Harry does with what comes back. This one pairs with the
    configured token, makes the folder if it is not there, and pushes a page — so it fails
    the day reMarkable changes the protocol, which is the failure that arrives at 06:30 on a
    morning nobody touched anything.

    Run it deliberately: `make test-live ARGS=tests/test_remarkable_connector.py`. Then look
    at the tablet.
    """
    found = load().get('connector', 'remarkable')
    assert found is not None, 'no remarkable connector on disk'
    assert found.target is not None, f'not configured: {found.reason}'

    page = Path('out/live-push.pdf')
    page.parent.mkdir(parents=True, exist_ok=True)
    _render_a_page(page)

    answer = found.target.push(page, 'Harry says hello — from make test-live')

    assert answer['where'] == found.target.folder
    assert answer['id']
    assert any(item['id'] == answer['id'] for item in found.target.documents()), 'it is not in the folder'


def _render_a_page(where: Path) -> None:
    """A real PDF at the Paper Pro's geometry, so the live test pushes the thing the morning
    page will be rather than a placeholder."""
    from weasyprint import HTML

    HTML(
        string="""
        <style>
          @page { size: 509.34pt 679.13pt; margin: 36pt; }
          body { font-family: Georgia, serif; }
        </style>
        <h1>Harry says hello</h1>
        <p>This page came from <code>make test-live</code>.</p>
        """
    ).write_pdf(where)


# ---------------------------------------------------------------------------
# Pairing, which happens once per machine
# ---------------------------------------------------------------------------


def test_pairing_writes_the_token_where_the_connector_reads_it(tmp_path):
    """The point of the whole command: a code a person can read off a web page becomes a
    token in the one file that is gitignored and beside the connector."""
    import remarkable_pair

    where = tmp_path / '.env.local'
    remarkable_pair.pair('abcd1234', where, register=lambda code: f'token-for-{code}')

    assert where.read_text(encoding='utf-8') == 'DEVICE_TOKEN=token-for-abcd1234\n'


def test_pairing_leaves_the_other_settings_alone(tmp_path):
    """Re-pairing must not silently move the documents back to the default folder."""
    import remarkable_pair

    where = tmp_path / '.env.local'
    where.write_text('FOLDER=Reading\nDEVICE_TOKEN=the-old-one\n', encoding='utf-8')

    remarkable_pair.pair('abcd1234', where, register=lambda code: 'the-new-one')

    assert where.read_text(encoding='utf-8') == 'FOLDER=Reading\nDEVICE_TOKEN=the-new-one\n'


def test_pairing_never_prints_the_token(tmp_path, capsys, monkeypatch):
    """It grants complete read and write over the tablet. It goes in a file, and nowhere a
    terminal buffer, a screen share or a paste can carry it.

    `_register` is replaced rather than called: it is the one line here that reaches
    reMarkable, and the gate never does.
    """
    import remarkable_pair

    monkeypatch.setattr(remarkable_pair, '_register', lambda code: TOKEN)
    where = tmp_path / '.env.local'

    assert remarkable_pair.main(['abcd1234', '--to', str(where)]) == 0

    said = capsys.readouterr().out + capsys.readouterr().err
    assert TOKEN not in said, 'the token was printed'
    assert where.read_text(encoding='utf-8') == f'DEVICE_TOKEN={TOKEN}\n'


def test_a_refused_code_says_to_get_another_and_quotes_nothing_back(tmp_path, monkeypatch):
    """A rejected pairing echoes the request back, and the request carried the code. The
    message says what to do and nothing about what was sent."""
    from remarkapy import RemarkableAPIError

    import remarkable_pair

    class Refusing:
        def register_device(self, code):
            raise RemarkableAPIError(f'400 rejected: code={code} token=leaked')

        def close(self):
            pass

    monkeypatch.setattr(remarkable_pair, 'Client', lambda **kwargs: Refusing())

    with pytest.raises(SystemExit) as refused:
        remarkable_pair.pair('abcd1234', tmp_path / '.env.local')

    assert 'get another from my.remarkable.com' in str(refused.value)
    assert 'leaked' not in str(refused.value) and 'code=' not in str(refused.value)


def test_pairing_makes_the_folder_if_the_connector_is_not_there_yet(tmp_path):
    import remarkable_pair

    where = tmp_path / 'connectors' / 'remarkable' / '.env.local'
    remarkable_pair.pair('abcd1234', where, register=lambda code: 'a-token')

    assert where.is_file()


def test_a_tablet_that_returns_nothing_is_an_error_rather_than_an_empty_token(tmp_path):
    """An empty DEVICE_TOKEN would load as "not set" and the connector would skip with a
    message about configuration, three steps away from what actually happened."""
    import remarkable_pair

    with pytest.raises(SystemExit, match='no token'):
        remarkable_pair.pair('abcd1234', tmp_path / '.env.local', register=lambda code: '')


def test_the_default_place_is_where_the_connector_reads_from():
    """Delete the connector's folder from this path and pairing writes somewhere Harry does
    not look, while printing that it worked."""
    import remarkable_pair

    assert str(remarkable_pair.WHERE) == '.harry/connectors/remarkable/.env.local'
    assert remarkable_pair.KEY == 'DEVICE_TOKEN'
    assert (REPO / '.harry' / 'connectors' / 'remarkable' / 'CONNECTOR.md').is_file()


# ---------------------------------------------------------------------------
# The two lines that build a real client, which nothing else here executes
# ---------------------------------------------------------------------------


@pytest.fixture
def no_network(monkeypatch, tmp_path):
    """A real remarkapy client, with httpx answering from memory and its default config
    path pointed somewhere disposable.

    Not an injected `http_client`: passing one flips remarkapy's own `injected_runtime`
    flag, which is what decides `persist_config` — so a test that injected would pass
    whether or not the caller asked for anything. Replacing `httpx.Client` leaves that
    decision exactly where production leaves it.

    **`DEFAULT_CONFIG_PATH` is moved because these tests exist to be broken.** The way you
    check a guard is to delete it and watch a test go red — and the guard here stops a
    device token being written to `~/.rmapi`. Without this line, checking it writes a real
    token into a real home directory. That happened once while this file was being written.
    """
    import remarkapy.configfile

    disposable = tmp_path / 'not-a-real-home' / '.rmapi'
    monkeypatch.setattr(remarkapy.configfile, 'DEFAULT_CONFIG_PATH', disposable)
    # Both, because `resolve_config_path` walks the candidates first and only falls back to
    # the default. The first candidate is `Path.home() / '.rmapi'` — which exists on the
    # machine this is being written on, so moving the fallback alone changes nothing.
    monkeypatch.setattr(remarkapy.configfile, 'candidate_config_paths', lambda: [disposable])

    def answered(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={'token': 'a-user-token'}, text='a-device-token')

    real = httpx.Client

    def in_memory(*args, **kwargs):
        kwargs.pop('transport', None)
        return real(*args, transport=httpx.MockTransport(answered), **kwargs)

    monkeypatch.setattr(httpx, 'Client', in_memory)


def the_home_copy() -> Path:
    """Where remarkapy writes a token when nobody stops it.

    Read from remarkapy rather than spelled out here, because it is a module-level constant
    computed from `pathlib.Path.home()` **at import time** — which is the whole reason these
    tests assert on a path instead of setting `HOME` and looking for a file. No environment
    variable can move it.
    """
    import remarkapy.configfile

    return remarkapy.configfile.DEFAULT_CONFIG_PATH


def test_the_tablet_client_is_built_with_the_ceiling_the_slack_line_quotes(tablet, no_network):
    """`_reach_remarkable` runs only in the live test, so every one of its settings could be
    deleted with the suite still green — and the Slack line says "did not answer within 30s",
    which would become a false statement about remarkapy's own default of 20.
    """
    built = _connector_module(tablet)['_reach_remarkable']('a-device-token')

    assert built._client.timeout.read == 30.0, 'the connector did not choose a ceiling of its own'
    assert built._interactive is False, 'an unattended Harry must never wait on input() at 06:30'


def test_the_tablet_client_never_writes_the_token_anywhere(tablet, no_network, monkeypatch):
    """The one place this token lives is the `.env.local` a person put it in.

    **This guards the property, not the keyword.** `_reach_remarkable` passes
    `persist_config=False`, and deleting it changes nothing today — remarkapy sets the same
    flag itself whenever a token is injected, which it always is here. Two guarantees for
    one property, and only one of them is visible in Harry's own code.

    So the assertion is on what comes out: a client that does not persist, and would not
    persist into a home directory if it did. That is what goes red the day somebody changes
    this function to read a config file instead of taking a token — which is the change that
    would otherwise put a tablet-wide credential in `~/.rmapi` with the suite green.
    """
    import remarkapy.auth

    def refuse(*args, **kwargs):
        raise AssertionError('the device token was written to disk')

    monkeypatch.setattr(remarkapy.auth, 'write_config', refuse)

    built = _connector_module(tablet)['_reach_remarkable']('a-device-token')
    built.refresh_user_token()

    assert built._persist_config is False, 'the client would write the token to disk'
    assert built._config_path != the_home_copy(), 'a write would land in a home directory'


def test_the_pairing_client_can_never_write_to_a_home_directory(no_network, tmp_path):
    """The credential that can rewrite every document on the tablet must not get a plaintext
    copy in a home directory.

    Both halves are asserted because it needs both. `persist_config=False` stops the write;
    `configfile` decides where a write would land if that keyword were ever dropped — and it
    has to, because remarkapy's default is computed from `pathlib.Path.home()` at import
    time and no environment variable can redirect it.
    """
    import remarkable_pair

    thrown_away = tmp_path / 'thrown-away' / '.rmapi'
    built = remarkable_pair._pairing_client(thrown_away)  # noqa: SLF001

    assert built._persist_config is False, 'the token would be written to disk'
    assert built._config_path == thrown_away, 'a write would land outside the throwaway'
    assert built._config_path != the_home_copy(), 'a write would land in a home directory'


def test_pairing_throws_the_config_directory_away(no_network, tmp_path, monkeypatch):
    """Whatever remarkapy may write, it is gone when the command returns."""
    import remarkable_pair

    seen: list[Path] = []
    real = remarkable_pair._pairing_client  # noqa: SLF001

    def watch(configfile: Path):
        seen.append(configfile)
        return real(configfile)

    monkeypatch.setattr(remarkable_pair, '_pairing_client', watch)
    where = tmp_path / 'connectors' / 'remarkable' / '.env.local'
    remarkable_pair.pair('abcd1234', where)

    assert where.is_file(), 'the token did not reach the file the connector reads'
    assert len(seen) == 1 and not seen[0].parent.exists(), 'the pairing directory outlived the command'


def test_a_listing_is_capped(tablet):
    """A folder that grew without a ceiling would be a year of mornings in the caller's
    context. Sixty documents in, fifty out, newest kept."""
    cloud = StandIn(
        folders=[Item(id='f', type='CollectionType', visibleName='Harry')],
        documents=[
            Item(id=f'd{n}', visibleName=f'Day {n}', parent='f', lastModified=str(1789384626339 + n)) for n in range(60)
        ],
    )

    found = connector(tablet(cloud=cloud)).documents()

    assert len(found) == 50
    assert found[0]['name'] == 'Day 59', 'the cap kept the oldest instead of the newest'


def test_a_smaller_limit_is_honoured(tablet):
    cloud = StandIn(
        folders=[Item(id='f', type='CollectionType', visibleName='Harry')],
        documents=[
            Item(id=f'd{n}', visibleName=f'Day {n}', parent='f', lastModified=str(1789384626339 + n)) for n in range(10)
        ],
    )

    assert len(connector(tablet(cloud=cloud)).documents(3)) == 3


async def test_something_that_is_not_a_pdf_is_refused_through_the_tool(tablet, tmp_path):
    """The suffix check is reached at the connector by another test. Production reaches it
    through MCP, and that is the path a bad argument actually arrives on."""
    cloud = StandIn()
    built = tablet(cloud=cloud, tools=BOTH_TOOLS)
    not_a_pdf = tmp_path / 'notes.txt'
    not_a_pdf.write_text('hello', encoding='utf-8')

    result = await through_mcp(
        built, tmp_path, 'remarkable_push_document', {'path': str(not_a_pdf), 'name': 'Notes'}, raise_on_error=False
    )

    assert result.is_error is True
    assert 'not a PDF' in str(result.content[0].text)  # type: ignore[union-attr] — an error is one TextContent
    assert cloud.pushed == []


def test_a_plain_pytest_run_cannot_reach_the_tablet():
    """The guard that exists because seven copies of a test page reached a real one.

    `-m 'not live'` lives in `addopts` rather than only in the Makefile, so the marker is
    opt-in however the suite is started. Nothing else watches that line: tidy it away and a
    bare `pytest tests/test_remarkable_connector.py` pushes real documents again.

    Collected in a subprocess with no `-m` of its own, which is exactly how somebody runs
    one file while working on it.
    """
    import subprocess

    collected = subprocess.run(
        ['python', '-m', 'pytest', '--collect-only', '-q', str(Path(__file__).name)],
        cwd=REPO / 'tests',
        capture_output=True,
        text=True,
        check=False,
    )

    assert 'test_a_real_page_reaches_a_real_tablet' not in collected.stdout, (
        'a plain pytest run would push a document to a real tablet'
    )
    assert 'deselected' in collected.stdout, collected.stdout[-400:]


def test_the_pairing_target_runs_the_pairing_script():
    """The criterion names `make remarkable-pair`. Renaming either side would leave it
    broken with a green gate, because every other test calls the script directly."""
    recipe = (REPO / 'Makefile').read_text(encoding='utf-8').partition('\nremarkable-pair:')[2].partition('\n\n')[0]

    assert 'scripts/remarkable_pair.py' in recipe
    assert '$(CODE)' in recipe, 'the target takes the code from the command line'
    assert 'my.remarkable.com/device/desktop/connect' in recipe, 'it should say where a code comes from'
