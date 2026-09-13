---
id: FEAT-260912-334932
title: Claude can call Harry from any session
track: full
created: 2026-09-12
touches: [core/main, core/mcp, core/registry, core/loader]
stories: [STORY-260913-1b32e7, STORY-260913-78d843, STORY-260913-c63603, STORY-260913-f28eb4]
decisions: [ADR-260912-b22e46, ADR-260913-18a8ae, ADR-260913-f38787]
---

# FEAT-260912-334932 — Claude can call Harry from any session

## Summary

The surface Harry exists to offer. Tools declared under .harry/tools/ become MCP tools with their body as the description; a job brief becomes an MCP prompt. Most tools stay out of the roster until tool search finds them, which is what keeps the surface cheap as it grows.

## Acceptance criteria

<!-- One box per scenario. These are what the pre-close-verifier builds its
     traceability matrix from. -->

- [x] A declared tool is callable over MCP with its TOOL.md body as the description, its frontmatter annotations, and a schema derived from the typed signature
- [x] A capability the loader skipped is not published, while /health still explains why
- [x] The roster comes back in name order, identical on every request
- [x] A tool with always_load false is absent from the roster until harry_find_tools reveals it, after which it lists and calls; a restart puts it back out
- [x] The roster is never empty: harry_find_tools is always there, so an all-deferred roster cannot happen at run time
- [x] A trigger: claude job's brief is an MCP prompt named for the job, rendered verbatim; a trigger: schedule job has none
- [x] A request with no bearer token, or the wrong one, is refused; the configured one gets the roster
- [x] A tool whose signature declares a principal is handed the caller's, and principal is absent from its input schema
- [x] A tool that raises returns an error with no traceback and no file path, and every other tool still works
- [x] A client reaching a running Harry over HTTP at /mcp with the configured token gets the roster
- [ ] `claude mcp list` shows harry connected — by inspection: needs a real Claude Code session, which a test client cannot stand in for

## Stories

<!-- Maintained by `board.py new-story`. -->
- [x] [[STORY-260913-1b32e7]] — Every tool a capability registered is callable over MCP
- [x] [[STORY-260913-78d843]] — Most tools stay out of the roster until somebody looks for one
- [x] [[STORY-260913-c63603]] — A job's brief is a prompt, so the scheduled task has nothing to copy
- [x] [[STORY-260913-f28eb4]] — Only a caller Harry recognises gets in, and a tool can find out who

## Notes

<!-- Appended by `board.py note`. -->
- **2026-09-13** — plan-verifier: WARN, no BLOCK. Five findings acted on: the harry_find_tools matching rule and its cap are now written down as a rule rather than left to taste; the restart that clears a reveal has a scenario; scenario 9 says what the error message contains and that steering text is the tool's job, not the transport's; the empty-search case has a line; and the claude mcp criterion is split into an automatable HTTP half and a 'by inspection' half. One correction to the verifier: its contract check reads registry.py:44-67 as Capability, but those lines are Context. Capability carries no declaration and no body, and the loader drops the Context it builds — so core/registry in touches is necessary, not defensive.
- **2026-09-13** — The by-inspection criterion is deliberately unticked. What was held against Harry: a real MCP client over HTTP with a bearer token, against a running 'python -m harry' — roster, prompts, a principal round trip, a deferred tool searched up and then called, and a refusal with no token. What was not: 'claude mcp list', which needs the owner's own Claude Code session. Note for whoever runs it — port 7430 is also where 'make probe' serves, so if /health there returns 404 the thing answering is the probe rather than Harry; and .mcp.json sends the probe's placeholder token unless HARRY_API_TOKEN is exported in the shell, because nothing exports .env.local. docs/mcp.md now says both.
- **2026-09-13** — Reflection: pre-close-verifier returned REQUEST CHANGES — 3 Critical, 5 Important, 2 Suggestions. All acted on except the two Suggestions (one commit carried three stories; a type: ignore comment, since fixed). Traceability 10/11 feature criteria and 25/25 story criteria; the eleventh is by inspection and stays unticked. Degraded paths exercised: no token, wrong token, unset token, a tool that raises, a tool that cannot be published, a search that matches nothing, an empty search, a notification that cannot be sent, and a call with no recognised token. Scope drift: none.

## Lessons Learned

### What worked

**Measuring the protocol before designing against it.** The plan was a per-conversation tool
roster: a tool you searched up appears for you and nobody else. Four requests against
`Context.session_id`, on the in-memory transport and over real HTTP with
`stateless_http=False`, returned four different ids. FastMCP 4.0.3 has nothing to key a
session on. Ten minutes of probing, before the requirements page was written, turned a
design that would have silently not worked into a documented limitation with the line to
come back to.

**Standing a real server up when the test transport could not carry the thing under test.**
FastMCP's in-memory transport carries no HTTP headers, so `Client(server, auth=…)` raises —
which means the bearer token, the one thing between Harry and anyone who can reach the port,
is structurally untestable in process. `tests/test_mcp_over_http.py` runs uvicorn on an
ephemeral port and knocks. Four refusals, a principal round trip, and `/health` alongside
`/mcp`, all over a real socket. It also found a bug nothing else could: see below.

**Running the finished thing.** Five capabilities, a real client, a bearer token: roster,
prompt, principal, a deferred tool searched up and then called, and a no-token refusal. Two
of this feature's three Critical findings were about claims that were ticked and not
asserted — running it is the cheapest check that the claims are about the same software.

### What to do differently

**`from harry.config import get_settings` binds at import.** `harry/mcp.py` did that, so the
door read whatever `harry.config` held when the module loaded while `principal_for_token`
read the current value — a Harry that refuses the token it is configured with. Import the
module and call `config.get_settings()` wherever the value can change under you. Only the
over-HTTP test could have caught it.

**A try/except in one module is not a property of the system.** The loader wraps every
capability in its own, which is what FEAT-260912-8a0ab0 shipped. `build_server` then
iterated the loaded capabilities with no guard at all, so one tool with an annotation that
would not validate stopped Harry from starting — and took `/health`, the endpoint that
exists to name the broken capability, with it. **When a feature establishes a property, the
next feature that touches the same objects has to be asked whether it still holds.**

**A prefix assertion is not an equality assertion.** "The description is the `TOOL.md` body,
verbatim" was checked with `description.startswith(…)`. Replacing the description with its
own first sentence — Harry summarising the text the requirements page calls the product —
left all 252 tests green. Where the claim is "verbatim", assert the whole string against the
file.

**Ask the deciding question of a guard with an early return.** `if not wanted: return []` in
the search read as obviously necessary and had no test. Deleting it passed the suite, and
`harry_find_tools("")` then pulled every deferred tool into the roster at once — the one
call that defeats the entire reason deferral exists.

### Patterns to reuse

- **`tests/test_mcp_over_http.py`** — uvicorn on port 0 in a thread, torn down in the
  fixture. Reach for it whenever the in-memory transport cannot carry what is under test:
  headers, auth, anything about the socket. `bearer()` in that file records that
  `auth=<string>` starts an OAuth flow rather than sending a header, which cost a debugging
  round.
- **`src/harry/mcp.py:_matching`** — a search that is a rule rather than a score:
  case-insensitive substring over name, namespace and body, name order, capped. A person can
  run it by hand and get the same answer, which is what keeps it on Harry's side of the
  boundary.
- **`Context.redact()` in `src/harry/registry.py`** — put scrubbing where the knowledge is,
  not where the first caller was. The loader had it and the MCP server did not, which is how
  a publish-time failure could have carried a credential into `/health`.
- **`tests/fixtures/capabilities/tools/broken_hints/`** — a capability that loads perfectly
  and cannot be published. The two moments are separate, and only a fixture that is broken in
  the second one proves the second one is guarded.

## Links

- Requirements: [[FEAT-260912-334932]]
- [[ADR-260912-b22e46]] — tools are one verb each, namespaced, leaning on MCP's own features
- [[ADR-260913-18a8ae]] — a tool exists because someone would ask for it
- [[ADR-260913-f38787]] — the roots list and the principal
