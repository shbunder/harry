"""The surface Harry exists to offer: the tools Claude calls, at `/mcp`.

Everything here publishes what the loader already found. Core does not know the name of
any tool, and adding one is still a folder.

Two things this gets right on purpose, because both are easy to get wrong:

**A tool's description is its `TOOL.md` body, served verbatim.** That text is what Claude
reads to decide whether to call the tool, and small changes to it move selection accuracy
more than almost anything else in the repo. Harry never edits, summarises or templates it —
that would be reasoning, and Harry does not reason.

**The roster is sent on every request.** Every tool in it and unused is rent, paid forever.
So a tool declaring `always_load: false` is genuinely absent from `tools/list` until
somebody searches for it with `harry_find_tools`, rather than merely flagged in metadata
that nothing reads.

A reveal is **server-wide and lasts until Harry restarts.** `Context.session_id` in FastMCP
4.0.3 is a fresh value on every request — on the in-memory transport and over HTTP with
`stateless_http=False` alike — so there is nothing to key a per-session roster on. That is
a disclosure change and not a permission change: every principal is already allowed every
tool, so one person's search costs everybody a few hundred tokens of roster rather than
access they did not have. Per-person permissions will need a stable session, and this is
the paragraph to come back to.
"""

from __future__ import annotations

import datetime as dt
import functools
import inspect
import logging
from collections.abc import Callable, Sequence
from typing import Any

import mcp.types as mt
from fastmcp import Context as CallContext, FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.prompts import Prompt
from fastmcp.server.auth.providers.jwt import StaticTokenVerifier
from fastmcp.server.dependencies import get_access_token
from fastmcp.server.middleware import Middleware
from fastmcp.tools import Tool

from harry import config
from harry.config import OWNER, Principal, principal_for_token
from harry.registry import LOADED, Capability, Catalogue
from harry.store import Store

LOG = logging.getLogger('harry.mcp')

FIND_TOOLS = 'harry_find_tools'
MARK_DONE = 'harry_mark_done'
DEFAULT_LIMIT = 10
MAX_LIMIT = 50

INSTRUCTIONS = """\
Harry does what you decide. Ask it for facts and it returns them; tell it what to make and
it makes it. It never chooses, ranks or summarises — that is your half.

Most tools are not in the list above. Call harry_find_tools with a word to bring the ones
you need into it.

When you finish a job Harry gave you a brief for, call harry_mark_done with its name.
Harry has no other way of knowing you were here.
"""


def build_server(catalogue: Catalogue, store: Store) -> FastMCP:
    """Everything the catalogue loaded, published.

    Built once per process, from one catalogue. Rebuilding is what a restart does, and it
    is what puts a revealed tool back out of the roster.
    """
    server = FastMCP(name='harry', instructions=INSTRUCTIONS, auth=_auth(), middleware=[SortedRoster()])

    deferred: dict[str, Capability] = {}
    published = 0
    for capability in catalogue.loaded:
        # Publishing happens after loading, so it can fail on its own: annotations that do
        # not validate, a signature FastMCP cannot derive a schema from. Without this the
        # failure escapes and Harry does not start at all — and the one endpoint that would
        # have named the broken capability is gone with it. One broken capability costs
        # exactly itself here too.
        try:
            if capability.kind == 'tool':
                _publish_tool(server, capability)
                published += 1
                if not _is_always_loaded(capability):
                    deferred[capability.name] = capability
            elif capability.kind == 'job':
                _publish_prompt(server, capability)
        except Exception as error:  # noqa: BLE001 — see the comment above
            catalogue.withdraw(capability, f'{type(error).__name__}: {error}')
            deferred.pop(capability.name, None)
            published -= 1 if capability.kind == 'tool' else 0
            LOG.warning('%s %s could not be published: %s', capability.kind, capability.name, capability.reason)

    server.add_tool(_find_tools_tool(server, deferred))
    server.add_tool(_mark_done_tool(catalogue, store))
    if deferred:
        server.disable(keys={_key(name) for name in deferred})
    LOG.info('%d tool(s) published, %d of them deferred', published, len(deferred))
    return server


# ---------------------------------------------------------------------------
# Who is asking
# ---------------------------------------------------------------------------


def _auth() -> StaticTokenVerifier:
    """One token, one principal — and an unconfigured Harry that authorises nobody.

    An empty configured token must never mean "anything matches". An unconfigured Harry
    behind the tunnel would then be serving the internet, which is the failure mode
    `principal_for_token` was written to refuse and this keeps refusing one layer up.
    """
    # `config.get_settings()`, not a `get_settings` imported by name. A name imported at
    # module load is bound to whatever `harry.config` held then, so the door here and
    # `principal_for_token` a few lines below could end up reading two different tokens —
    # which is a Harry that refuses the token it is configured with.
    configured = config.get_settings().api_token.get_secret_value()
    tokens = {configured: {'client_id': OWNER.id, 'scopes': []}} if configured else {}
    return StaticTokenVerifier(tokens)


def caller() -> Principal:
    """The principal behind this call, or a refusal.

    Resolved from the bearer token the request already carried, so a tool never has to be
    told who is asking by the caller — which is the only version of this worth anything.
    """
    token = get_access_token()
    found = principal_for_token(token.token) if token is not None else None
    if found is None:
        raise ToolError('this call carries no token Harry recognises')
    return found


def _wants_principal(function: Callable[..., Any]) -> bool:
    return 'principal' in inspect.signature(function).parameters


def _filling_in_the_principal(function: Callable[..., Any]) -> Callable[..., Any]:
    """Hide `principal` from the schema and fill it in from the token.

    A `principal` the caller could pass would be a caller claiming to be somebody, which is
    worth nothing. Removing it from the signature is what removes it from the schema
    FastMCP derives, so the model never sees a field it could get wrong.
    """
    signature = inspect.signature(function)
    without = signature.replace(parameters=[p for name, p in signature.parameters.items() if name != 'principal'])

    if inspect.iscoroutinefunction(function):

        @functools.wraps(function)
        async def call_async(*args: Any, **kwargs: Any) -> Any:
            return await function(*args, principal=caller(), **kwargs)

            # Set after `wraps`, which copies `__wrapped__` and would otherwise send

        # `inspect.signature` back to the original — principal and all.
        call_async.__signature__ = without  # type: ignore[attr-defined]
        return call_async

    @functools.wraps(function)
    def call(*args: Any, **kwargs: Any) -> Any:
        return function(*args, principal=caller(), **kwargs)

    # Same reason as the async branch above.
    call.__signature__ = without  # type: ignore[attr-defined]
    return call


# ---------------------------------------------------------------------------
# Publishing what the loader found
# ---------------------------------------------------------------------------


def _publish_tool(server: FastMCP, capability: Capability) -> None:
    declaration = _declaration(capability)
    function = capability.target
    if function is None or capability.context is None:  # pragma: no cover — the loader refuses both
        return

    hints = declaration.get('annotations') or {}
    server.add_tool(
        Tool.from_function(
            _filling_in_the_principal(function) if _wants_principal(function) else function,
            name=capability.name,
            description=capability.context.body,
            annotations=mt.ToolAnnotations(**hints),
        )
    )


def _publish_prompt(server: FastMCP, capability: Capability) -> None:
    """A `trigger: claude` job's brief, as an MCP prompt named for the job.

    That is what prompts are for in the protocol: the scheduled task invokes it by name
    rather than carrying a copy of the brief that drifts from the file, and the job shows
    up in any client's prompt picker for nothing.

    A `trigger: schedule` job's body is documentation. Nothing serves it.
    """
    declaration = _declaration(capability)
    if declaration.get('trigger') != 'claude' or capability.context is None:
        return

    brief = capability.context.body

    def render() -> str:
        return brief

    server.add_prompt(
        Prompt.from_function(render, name=capability.name, description=str(declaration.get('description', '')))
    )


def _declaration(capability: Capability) -> dict[str, Any]:
    return dict(capability.context.declaration) if capability.context is not None else {}


def _is_always_loaded(capability: Capability) -> bool:
    return bool(_declaration(capability).get('always_load'))


def _key(name: str) -> str:
    """How FastMCP addresses one unversioned tool in `disable()` and `enable()`."""
    return f'tool:{name}@'


# ---------------------------------------------------------------------------
# The roster
# ---------------------------------------------------------------------------


class SortedRoster(Middleware):
    """The roster comes back in name order, every time.

    The MCP specification says deterministic ordering improves prompt-cache hit rates.
    Filesystem order is not deterministic, and it is what you get by accident.
    """

    async def on_list_tools(self, context: Any, call_next: Any) -> Sequence[Tool]:
        return sorted(await call_next(context), key=lambda tool: tool.name)


def _find_tools_tool(server: FastMCP, deferred: dict[str, Capability]) -> Tool:
    """Core's own tool, and the only one that is always in the roster.

    It has to be core's rather than a capability's: it needs the server object to reveal
    anything, and a roster with nothing in it is a 400 from the API rather than a slow
    path — so the one tool that can never be deferred cannot be something somebody might
    delete.
    """

    async def harry_find_tools(query: str, ctx: CallContext, limit: int = DEFAULT_LIMIT) -> dict[str, Any]:
        if limit < 1 or limit > MAX_LIMIT:
            raise ToolError(f'limit must be between 1 and {MAX_LIMIT}, got {limit}')

        matches = _matching(query, deferred)
        shown = matches[:limit]
        if shown:
            server.enable(keys={_key(capability.name) for capability in shown})
            await _say_the_roster_changed(ctx)

        return {
            'query': query,
            'found': [{'name': capability.name, 'description': _summary(capability)} for capability in shown],
            'note': _note(query, matches, shown, limit),
        }

    harry_find_tools.__doc__ = None
    return Tool.from_function(
        harry_find_tools,
        name=FIND_TOOLS,
        description=(
            'Find the tools Harry has that are not in your list yet, and add them to it.\n\n'
            'Most of what Harry can do is kept out of the tool list until you ask for it, so '
            'the list stays small. Pass a word — a source, a thing, a verb — and every tool '
            'whose name or description contains it is returned and added to your tools from '
            'then on.\n\n'
            'Reach for this whenever you want Harry to do something and cannot see a tool for '
            'it. Do not reach for it to re-find a tool you can already see.'
        ),
        annotations=mt.ToolAnnotations(read_only_hint=True, idempotent_hint=True, open_world_hint=False),
    )


def _mark_done_tool(catalogue: Catalogue, store: Store) -> Tool:
    """Core's own tool, and the only way Harry can learn a Claude-triggered job happened.

    Harry does not own the clock for anything that needs judgement, and the cost of that is
    that it cannot tell a morning page that was never built from one it simply did not
    watch. This is the sentence that closes the gap, and every `trigger: claude` brief ends
    by asking for it.

    Always in the roster, because a brief cannot search for a tool it needs.
    """

    def harry_mark_done(job: str) -> dict[str, str]:
        found = catalogue.get('job', job)
        if found is None or found.status != LOADED:
            known = ', '.join(sorted(c.name for c in catalogue.loaded if c.kind == 'job')) or 'none are loaded'
            raise ToolError(f'{job!r} is not a job Harry is running. Jobs it has: {known}.')

        at = dt.datetime.now(dt.UTC)
        store.mark_finished(job, at)
        LOG.info('%s marked done at %s', job, at.isoformat())
        return {'job': job, 'finished': at.isoformat()}

    return Tool.from_function(
        harry_mark_done,
        name=MARK_DONE,
        description=(
            'Tell Harry you have finished a job it briefed you for.\n\n'
            'Harry does not fire these jobs — a scheduled task does — so it has no way of '
            'knowing the work happened unless you say so. Call this once, at the end, with '
            'the job name from the brief you were given.\n\n'
            'If you do not, Harry will report the job as missed at its deadline, about work '
            'you actually did. Calling it for something that is not a job is an error, so '
            'use the name exactly as the brief gives it.'
        ),
        annotations=mt.ToolAnnotations(read_only_hint=False, idempotent_hint=True, open_world_hint=False),
    )


def _matching(query: str, deferred: dict[str, Capability]) -> list[Capability]:
    """Every deferred tool whose name, namespace or body contains the query.

    Substring, case-insensitive, no stemming and no ranking, in name order. A rule a
    person could follow by hand — a relevance score would be an opinion, and an opinion is
    judgement, which is Claude's half of the boundary rather than Harry's.
    """
    wanted = query.strip().lower()
    if not wanted:
        return []
    found = [
        capability for name, capability in deferred.items() if wanted in name.lower() or wanted in _haystack(capability)
    ]
    return sorted(found, key=lambda capability: capability.name)


def _haystack(capability: Capability) -> str:
    declaration = _declaration(capability)
    body = capability.context.body if capability.context is not None else ''
    return f'{declaration.get("namespace", "")}\n{body}'.lower()


def _summary(capability: Capability) -> str:
    """The declaration's one-line description. The full body arrives with the tool itself."""
    return str(_declaration(capability).get('description', '')).strip()


def _note(query: str, matches: list[Capability], shown: list[Capability], limit: int) -> str:
    if not matches:
        return f'Nothing Harry has matches {query!r}. Try a different word, or a broader one.'
    if len(matches) > len(shown):
        return (
            f'{len(matches)} tools match {query!r} and the first {limit} are here, in name order. '
            'Search more narrowly, or raise limit.'
        )
    return f'Added {len(shown)} tool(s) to your list. They stay there until Harry restarts.'


async def _say_the_roster_changed(ctx: CallContext) -> None:
    """Tell the client to look again, so a revealed tool becomes callable.

    Best effort. The answer already names what was revealed, so a client that never hears
    this is worse off by one round trip rather than unable to continue — and failing the
    search because the courtesy notification did not go out would be the wrong trade.
    """
    try:
        await ctx.send_notification(mt.ToolListChangedNotification(method='notifications/tools/list_changed'))
    except Exception as error:  # noqa: BLE001 — see the docstring: the reveal already happened
        LOG.warning('could not send tools/list_changed: %s', error)
