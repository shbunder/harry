"""What Claude can reach, and what it cannot.

Every test goes through an MCP client against a server built from a real catalogue, because
"can a client call this tool" is the question and calling the function directly answers a
different one. `Client(server)` connects to the object in process, so none of this needs a
port or a tunnel — the one test that does want a real socket says so at its own assertion.
"""

from __future__ import annotations

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError
from mcp.types import TextContent
from pydantic import SecretStr

# Imported as a module as well as by name: the fixture below is called `harry`, so an
# `import harry.mcp` inside a test would shadow it with the package.
from harry import mcp as mcp_module
from harry.loader import load
from harry.mcp import DEFAULT_LIMIT, FIND_TOOLS, MARK_DONE, MAX_LIMIT, build_server
from harry.store import Store

from .test_loader import root_with

TOKEN = 'a-token-for-the-tests-only'


@pytest.fixture
def harry(tmp_path, monkeypatch):
    """A Harry whose capabilities are whatever the test asks for, with a known token."""
    import harry.config

    monkeypatch.delenv('HARRY_ICLOUD_APP_PASSWORD', raising=False)
    settings = harry.config.Settings(api_token=SecretStr(TOKEN), data_dir=tmp_path / 'data')
    monkeypatch.setattr(harry.config, 'get_settings', lambda: settings)

    def build(*capabilities: str):
        root = root_with(tmp_path / 'root', *capabilities)
        return build_server(load([root]), Store(tmp_path / 'jobs.json'))

    return build


def client(server) -> Client:
    """In process, and with no token.

    FastMCP's in-memory transport carries no HTTP headers, so it cannot carry a bearer
    token either — `Client(server, auth=…)` raises outright. Everything about publishing,
    deferral and prompts is testable here; the door itself is not, and
    `tests/test_mcp_over_http.py` takes that half over a real socket.
    """
    return Client(server)


async def roster(server) -> list[str]:
    async with client(server) as connected:
        return [tool.name for tool in await connected.list_tools()]


# ---------------------------------------------------------------------------
# Publishing what the loader registered
# ---------------------------------------------------------------------------


async def test_a_declared_tool_is_callable_and_described_by_its_own_body(harry):
    server = harry('connectors/weather', 'tools/weather_forecast')

    async with client(server) as connected:
        tools = {tool.name: tool for tool in await connected.list_tools()}
        assert 'weather_forecast' in tools

        published = tools['weather_forecast']
        description = published.description or ''
        assert description.startswith("Returns today's forecast for the configured place")
        assert '---' not in description, 'the frontmatter leaked into the description'

        result = await connected.call_tool('weather_forecast', {'day': 'tomorrow'})

    assert result.data == {'day': 'tomorrow', 'summary': 'grey, as ever'}


async def test_the_annotations_are_the_ones_in_the_frontmatter(harry):
    """This is how a client gates a tool that reaches your tablet without gating one that
    reads a feed, and nothing else carries that signal."""
    server = harry('connectors/weather', 'tools/weather_forecast')

    async with client(server) as connected:
        published = {tool.name: tool for tool in await connected.list_tools()}['weather_forecast']

    assert published.annotations is not None
    assert published.annotations.read_only_hint is True
    assert published.annotations.idempotent_hint is True


async def test_the_input_schema_comes_from_the_signature_and_is_declared_nowhere(harry):
    """Declaring it in the frontmatter as well would be a second copy of what the code
    already knows, and the two would drift."""
    server = harry('connectors/weather', 'tools/weather_forecast')

    async with client(server) as connected:
        published = {tool.name: tool for tool in await connected.list_tools()}['weather_forecast']

    assert set(published.input_schema['properties']) == {'day'}
    assert published.input_schema['properties']['day']['type'] == 'string'


async def test_a_tool_the_loader_skipped_is_not_published(harry):
    """Worse than missing: Claude picks it, and a missing credential reads as a broken
    tool."""
    server = harry('connectors/icloud', 'tools/icloud_list_events', 'connectors/weather', 'tools/weather_forecast')

    assert 'icloud_list_events' not in await roster(server)
    assert 'weather_forecast' in await roster(server)


async def test_a_tool_with_no_python_behind_it_never_reaches_the_roster(harry):
    """A TOOL.md written before the tool.py beside it. The loader refuses it, so there is
    nothing here for Claude to pick and fail on."""
    server = harry('tools/paper_push', 'connectors/weather', 'tools/weather_forecast')

    assert 'paper_push' not in await roster(server)


async def test_the_roster_is_in_name_order_and_the_same_every_time(harry):
    """The specification says deterministic ordering improves prompt-cache hit rates.
    Filesystem order is not deterministic, and it is what you get by accident."""
    server = harry('connectors/weather', 'tools/weather_forecast', 'tools/news_failing', 'tools/account_whoami')

    first = await roster(server)
    second = await roster(server)

    assert first == sorted(first)
    assert first == second


# ---------------------------------------------------------------------------
# A tool that fails
# ---------------------------------------------------------------------------


async def test_a_failing_tool_returns_its_own_message_and_no_traceback(harry):
    """Steering text is the tool's job — the only thing that knows what to try is the tool
    that failed. Harry's part is to carry that sentence through and add nothing."""
    server = harry('tools/news_failing', 'connectors/weather', 'tools/weather_forecast')

    async with client(server) as connected:
        result = await connected.call_tool('news_failing', {}, raise_on_error=False)
        still_working = await connected.call_tool('weather_forecast', {})

    assert result.is_error
    message = ' '.join(block.text for block in result.content if isinstance(block, TextContent))
    assert 'news_failing' in message
    assert 'no articles since 05:00, try since=yesterday' in message
    for leak in ('Traceback', '.py', 'line ', 'harry/mcp'):
        assert leak not in message, f'{leak!r} reached the caller'

    assert still_working.data == {'day': 'today', 'summary': 'grey, as ever'}


# ---------------------------------------------------------------------------
# Deferral: most tools are not in the roster
# ---------------------------------------------------------------------------


async def test_a_deferred_tool_is_absent_and_an_always_loaded_one_is_not(harry):
    server = harry('connectors/weather', 'tools/weather_forecast', 'tools/notes_search')

    listed = await roster(server)

    assert 'weather_forecast' in listed
    assert FIND_TOOLS in listed
    assert 'notes_search' not in listed


async def test_searching_reveals_a_tool_and_then_it_lists_and_calls(harry):
    server = harry('tools/notes_search')

    async with client(server) as connected:
        assert 'notes_search' not in [t.name for t in await connected.list_tools()]

        answer = (await connected.call_tool(FIND_TOOLS, {'query': 'note'})).data
        assert [found['name'] for found in answer['found']] == ['notes_search']
        assert answer['found'][0]['description'] == 'Find a note by a word in its title or its text'

        assert 'notes_search' in [t.name for t in await connected.list_tools()]
        result = await connected.call_tool('notes_search', {'query': 'groceries'})

    assert result.data[0]['matched'] == 'groceries'


async def test_revealing_tells_the_client_to_look_again(harry):
    """The client only re-lists when it is told to. Without the notification a revealed
    tool sits in the roster that nobody asked for again."""
    server = harry('tools/notes_search')
    heard: list[str] = []

    async def note_it(message):
        heard.append(getattr(message, 'method', type(message).__name__))

    async with Client(server, message_handler=note_it) as connected:
        await connected.call_tool(FIND_TOOLS, {'query': 'note'})

    assert 'notifications/tools/list_changed' in heard


async def test_the_search_matches_the_namespace_and_the_body_not_only_the_name(harry):
    """A word from the description is what somebody actually has. "notebook" appears only
    in the body."""
    server = harry('tools/notes_search')

    async with client(server) as connected:
        by_body = (await connected.call_tool(FIND_TOOLS, {'query': 'NOTEBOOK'})).data

    assert [found['name'] for found in by_body['found']] == ['notes_search']


async def test_a_search_that_matches_nothing_says_so_and_reveals_nothing(harry):
    server = harry('tools/notes_search')

    async with client(server) as connected:
        answer = (await connected.call_tool(FIND_TOOLS, {'query': 'dishwasher'})).data
        after = [t.name for t in await connected.list_tools()]

    assert answer['found'] == []
    assert 'dishwasher' in answer['note']
    assert 'notes_search' not in after


async def test_a_limit_outside_the_range_is_refused(harry):
    """Anything that searches needs a cap, and a cap nobody can step over."""
    server = harry('tools/notes_search')

    async with client(server) as connected:
        with pytest.raises(ToolError, match=str(MAX_LIMIT)):
            await connected.call_tool(FIND_TOOLS, {'query': 'note', 'limit': MAX_LIMIT + 1})
        with pytest.raises(ToolError):
            await connected.call_tool(FIND_TOOLS, {'query': 'note', 'limit': 0})


async def test_a_capped_answer_says_to_search_more_narrowly(harry, tmp_path):
    """Truncation that does not say it truncated is how somebody concludes Harry has three
    tools when it has thirty."""
    import shutil

    root = root_with(tmp_path / 'many', 'tools/notes_search')
    for index in range(DEFAULT_LIMIT + 2):
        folder = root / 'tools' / f'notes_search{index}'
        shutil.copytree(root / 'tools' / 'notes_search', folder)
        declaration = folder / 'TOOL.md'
        declaration.write_text(
            declaration.read_text(encoding='utf-8').replace('name: notes_search', f'name: notes_search{index}'),
            encoding='utf-8',
        )
        (folder / 'tool.py').write_text(
            'from harry.sdk import Context, Registry\n\n\n'
            'def register(registry: Registry, context: Context) -> None:\n'
            f'    registry.tool(lambda: {index})\n',
            encoding='utf-8',
        )

    server = build_server(load([root]), Store(tmp_path / 'jobs.json'))
    async with client(server) as connected:
        answer = (await connected.call_tool(FIND_TOOLS, {'query': 'notes'})).data

    assert len(answer['found']) == DEFAULT_LIMIT
    assert 'more narrowly' in answer['note']


async def test_the_roster_is_never_empty_even_when_every_tool_is_deferred(harry):
    """A roster with nothing in it is a 400 from the API, not a slow path: the search tool
    needs something alongside it, and here it is the something."""
    server = harry('tools/notes_search')

    assert await roster(server) == sorted([FIND_TOOLS, MARK_DONE])


async def test_a_restart_puts_a_revealed_tool_back_out_of_the_roster(harry, tmp_path):
    """The whole mitigation for a roster that would otherwise only grow. A reveal that
    survived a restart would be permanent state nobody asked for."""
    root = root_with(tmp_path / 'root', 'tools/notes_search')

    revealed = build_server(load([root]), Store(tmp_path / 'jobs.json'))
    async with client(revealed) as connected:
        await connected.call_tool(FIND_TOOLS, {'query': 'note'})
        assert 'notes_search' in [t.name for t in await connected.list_tools()]

    restarted = build_server(load([root]), Store(tmp_path / 'jobs.json'))
    assert 'notes_search' not in await roster(restarted)


# ---------------------------------------------------------------------------
# A job's brief is a prompt
# ---------------------------------------------------------------------------


async def test_a_claude_triggered_job_is_a_prompt_rendered_verbatim(harry):
    """So the scheduled task invokes it by name instead of carrying a copy of the brief
    that drifts from the file."""
    server = harry('jobs/morning-page', 'connectors/weather', 'tools/weather_forecast')

    async with client(server) as connected:
        prompts = {prompt.name: prompt for prompt in await connected.list_prompts()}
        assert 'morning-page' in prompts
        assert (prompts['morning-page'].description or '').startswith("The day's weather")

        rendered = await connected.get_prompt('morning-page')

    content = rendered.messages[0].content
    assert isinstance(content, TextContent)
    text = content.text
    assert text.startswith("Ask Harry for today's candidates.")
    assert 'digest_build' in text
    assert '---' not in text


async def test_a_scheduled_job_has_no_prompt(harry):
    """Nothing reads a heuristic job's body. It is documentation for whoever opens the
    file in three weeks."""
    server = harry('jobs/refresh', 'jobs/morning-page')

    async with client(server) as connected:
        names = [prompt.name for prompt in await connected.list_prompts()]

    assert names == ['morning-page']


async def test_a_job_the_loader_skipped_has_no_prompt(harry, tmp_path):
    """A prompt for a job that is not running would be a brief telling Claude to call
    tools that are not there."""
    harry('jobs/morning-page')
    root = tmp_path / 'root'
    (root / 'jobs' / 'morning-page' / 'JOB.md').write_text(
        (root / 'jobs' / 'morning-page' / 'JOB.md')
        .read_text(encoding='utf-8')
        .replace('enabled: true', 'enabled: false'),
        encoding='utf-8',
    )

    async with client(build_server(load([root]), Store(tmp_path / 'jobs.json'))) as connected:
        assert await connected.list_prompts() == []


# ---------------------------------------------------------------------------
# The claims that were ticked and not asserted
# ---------------------------------------------------------------------------


async def test_the_description_is_the_body_and_not_a_version_of_it(harry, tmp_path):
    """Equality, not a prefix. The body is the text Claude reads to choose, and a check
    that only looks at the first line passes just as happily against a Harry that
    summarises every description down to its first sentence."""
    server = harry('connectors/weather', 'tools/weather_forecast')
    declaration = (tmp_path / 'root' / 'tools' / 'weather_forecast' / 'TOOL.md').read_text(encoding='utf-8')
    body = declaration.partition('\n---')[2].strip()

    async with client(server) as connected:
        published = {tool.name: tool for tool in await connected.list_tools()}['weather_forecast']

    assert published.description == body
    assert '\n' in body, 'a one-line body would make this assertion weaker than it looks'


async def test_an_empty_query_reveals_nothing(harry):
    """Deferral is the whole cost argument, and one empty-string call would defeat it:
    every deferred tool into the roster at once, for free."""
    server = harry('tools/notes_search')

    async with client(server) as connected:
        for query in ('', '   ', '\t\n'):
            answer = (await connected.call_tool(FIND_TOOLS, {'query': query})).data
            assert answer['found'] == [], f'{query!r} revealed something'
        assert [t.name for t in await connected.list_tools()] == sorted([FIND_TOOLS, MARK_DONE])


async def test_a_capability_that_cannot_be_published_costs_only_itself(harry):
    """Loading and publishing are two moments, and the loader's try/except only covers the
    first. A tool whose annotations do not validate loads cleanly and fails here — and
    before this was guarded it took Harry down, /health with it."""
    server = harry('tools/broken_hints', 'connectors/weather', 'tools/weather_forecast')

    listed = await roster(server)

    assert 'broken_hints' not in listed
    assert 'weather_forecast' in listed


async def test_health_says_why_a_capability_could_not_be_published(harry, tmp_path):
    """Otherwise it is the one failure Harry hides: loaded as far as anything can see, and
    absent from the roster with no reason anywhere."""
    root = root_with(tmp_path / 'root', 'tools/broken_hints', 'connectors/weather', 'tools/weather_forecast')
    catalogue = load([root])
    build_server(catalogue, Store(tmp_path / 'jobs.json'))

    rows = {row['name']: row for row in catalogue.as_health()['capabilities']}
    assert rows['broken_hints']['status'] == 'skipped'
    assert 'readOnlyHint' in rows['broken_hints']['reason']
    assert rows['weather_forecast']['status'] == 'loaded'


async def test_a_call_with_no_recognised_token_is_refused_inside_the_tool(harry, monkeypatch):
    """The last line between a tool and an unidentified caller. In process there is no
    token at all, which is exactly the shape of a request that got past the door with
    nothing on it."""
    monkeypatch.setattr(mcp_module, 'get_access_token', lambda: None)
    server = harry('tools/account_whoami')

    async with client(server) as connected:
        with pytest.raises(ToolError, match='recognises'):
            await connected.call_tool('account_whoami', {})


async def test_a_reveal_survives_a_notification_that_cannot_be_sent(harry, monkeypatch, caplog):
    """The notification is a courtesy — the answer already names what was revealed. Failing
    the search because the courtesy did not go out would be the wrong trade."""
    import logging

    async def refuse(*args, **kwargs):
        raise RuntimeError('the client hung up')

    monkeypatch.setattr(mcp_module.CallContext, 'send_notification', refuse)
    server = harry('tools/notes_search')

    with caplog.at_level(logging.WARNING, logger='harry.mcp'):
        async with client(server) as connected:
            answer = (await connected.call_tool(FIND_TOOLS, {'query': 'note'})).data
            listed = [t.name for t in await connected.list_tools()]

    assert [found['name'] for found in answer['found']] == ['notes_search']
    assert 'notes_search' in listed, 'the reveal was lost with the notification'
    assert 'could not send tools/list_changed' in caplog.text


# ---------------------------------------------------------------------------
# The only way Harry can learn a Claude-triggered job happened
# ---------------------------------------------------------------------------


async def test_marking_a_job_done_records_when(harry, tmp_path):
    """Harry does not fire these jobs, so it has no way of knowing the work happened unless
    Claude says so. This is that sentence."""
    server = harry('jobs/morning-page')

    async with client(server) as connected:
        answer = (await connected.call_tool(MARK_DONE, {'job': 'morning-page'})).data

    assert answer['job'] == 'morning-page'
    assert Store(tmp_path / 'jobs.json').last_finished('morning-page') is not None


async def test_the_record_is_there_after_a_restart(harry, tmp_path):
    """A restart that lost it would have the watchdog report a missed deadline about a page
    delivered an hour earlier — a false alarm on every deploy."""
    async with client(harry('jobs/morning-page')) as connected:
        await connected.call_tool(MARK_DONE, {'job': 'morning-page'})

    restarted = build_server(load([tmp_path / 'root']), Store(tmp_path / 'jobs.json'))
    async with client(restarted) as connected:
        await connected.list_tools()

    assert Store(tmp_path / 'jobs.json').last_finished('morning-page') is not None


async def test_marking_something_that_is_not_a_job_is_an_error_that_names_it(harry):
    """A typo that wrote a record nothing reads would be worse than an error: the watchdog
    would go on alerting and the caller would think it had been heard."""
    server = harry('jobs/morning-page')

    async with client(server) as connected:
        with pytest.raises(ToolError) as refused:
            await connected.call_tool(MARK_DONE, {'job': 'morning-pages'})

    assert 'morning-pages' in str(refused.value)
    assert 'morning-page' in str(refused.value), 'the error should say what Harry does have'


async def test_marking_done_is_always_in_the_roster(harry):
    """A brief cannot search for a tool it needs — it is text Claude is handed, not a
    conversation."""
    server = harry('tools/notes_search')

    assert MARK_DONE in await roster(server)
