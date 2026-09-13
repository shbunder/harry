---
id: FEAT-260913-007e6f
title: Harry can post to any channel it has been invited to, not just one
track: full
created: 2026-09-13
touches: [connectors/slack, tools/slack_post, core/registry, core/loader, docs]
stories: [STORY-260913-1f89fb, STORY-260913-c9ea14]
decisions: [ADR-260913-210e08, ADR-260913-18a8ae, ADR-260912-b22e46]
---

# FEAT-260913-007e6f — Harry can post to any channel it has been invited to, not just one

## Summary

Claude chooses where a message goes, according to what the message is: a failure to the alerting channel, a finished piece of work to the channel the people who asked for it are in. That is a tool rather than a setting, and exposing one is an explicit choice.

It also closes a gap nothing had noticed. A tool declares `requires: [slack]`, the loader refuses the tool when the connector is missing — and nothing ever hands the connector over. Every tool so far has been a fixture returning a dictionary. This is the first real one, and it needs the other half of that contract.

## Acceptance criteria

<!-- One box per scenario. These are what the pre-close-verifier builds its
     traceability matrix from. -->

- [x] A tool declaring `requires: [slack]` is handed what that connector registered, in context.connectors, and nothing it did not declare
- [x] A connector that registered nothing, and a connector that was never declared, are both refused at start-up with a sentence — not a KeyError in /health
- [x] slack_post(channel, text) posts one line to that channel and says which channel it went to
- [x] slack_post with no channel uses CHANNEL, and alerts Harry raises itself still go there unchanged
- [x] Posting to a channel the bot is not in comes back as an error naming the channel and saying to invite the bot
- [x] slack_post is deferred and harry_find_tools("slack") finds it, and an all-deferred .harry/tools/ passes the gate now that core always publishes two loaded tools of its own
- [x] The Slack connector declares `provides: [slack_post]`, which is where the choice to expose it is written down
- [x] slack_post carries readOnlyHint false, destructiveHint false, idempotentHint false and openWorldHint true
- [x] With no Slack credential the tool is skipped rather than offered, and Harry starts
- [x] The tool's module imports harry.sdk and nothing else, and core names neither slack nor slack_post
- [x] docs/alerting.md — the page a person operates — says Claude picks the channel and that inviting the bot is the only thing that widens where it may post
- [x] Every page that describes what a capability is handed says nine fields — docs/capabilities.md, .harry/README.md and the three /new-* skills
- [x] The loader's requirements page points at the ADR that amended it, so a reader who opens the natural page is not told something untrue

## Stories

<!-- Maintained by `board.py new-story`. -->
- [x] [[STORY-260913-1f89fb]] — A tool can use the connector it declared, without importing it
- [x] [[STORY-260913-c9ea14]] — Claude picks the channel, and the bot's invitations decide the rest

## Notes

<!-- Appended by `board.py note`. -->
- **2026-09-13** — Reflection: pre-close-verifier returned REQUEST CHANGES — 0 Critical, 4 Important, 3 Suggestions; all four Important acted on, plus two of the three Suggestions (the third was a commit-naming note). Traceability 13/13 feature criteria and 19/19 story criteria; two criteria were reworded because the design moved during implementation and the board said what had been planned rather than what shipped. Degraded paths exercised: no credential, a connector that registered nothing, a connector never declared, not_in_channel, channel_not_found, invalid_auth, an unknown Slack code, a non-JSON 502, a refused connection and a read timeout. Scope drift: two gate rules changed in opposite directions, both named on the requirements page before the code.

## Lessons Learned

### What worked

**Deleting a thing to see whether anything notices.** `provides:` was ticked as a criterion
and was decoration — removing it from the connector left the whole suite green. That turned
into a gate rule with real teeth: a name in the list must be a tool that exists, and a tool
namespaced after a connector must appear in that connector's list. **Do this to every
declaration field you add, not only to code.**

**Retiring a rule instead of working around it.** `check_capabilities.py` refused an
all-deferred `.harry/tools/` because an empty tool list is rejected by the API. True when
written; Harry now publishes two tools of its own that never defer, so the premise had
quietly died. The rule is gone and the comment where it used to be names the test that
would bring it back — `tests/test_mcp.py::test_the_roster_is_never_empty_even_when_every_tool_is_deferred`.

**Writing the ADR before the code.** The alerting feature's lesson, applied. It paid twice:
it forced the kind/role distinction to be stated, and when the design moved during
implementation the record was there to correct rather than to write from memory.

### What to do differently

**A criterion can be ticked, untested and simply false.** "Reaching for a connector you did
not declare is refused with a sentence rather than a KeyError" was ticked because the half
that was already true — it is skipped — was the half that got checked. `/health` said
`KeyError: 'weather'`. **When a criterion has two clauses, ask which one the test actually
exercises.**

**Test through the surface the caller uses.** The tool's default channel was asserted on
`Slack.send`, one layer beneath the tool. Making the tool's `channel` argument required
broke the criterion outright and left all 358 tests green. Third feature running where this
exact shape appeared.

**The ADR moved during implementation and nobody would have known.** It described the
capability's own `KeyError` becoming the skip; the loader refuses up front with a better
sentence. Both are defensible; only one shipped. **When the design changes under you, the
record is what changes with it.**

**The page a person operates is not the page that documents the module.**
`docs/capabilities.md` and `docs/mcp.md` both covered the wiring. `docs/alerting.md` — the
one somebody opens to set Slack up — still said "invite the bot to the channel you want",
singular, and never mentioned that Claude can now choose.

### Two traps worth knowing

**A stale `__pycache__` will lie to you.** A source file and its bytecode written inside the
same second leave Python running the old code, and a correct fix looks broken. It cost
twenty minutes here. Export `PYTHONDONTWRITEBYTECODE=1` before any run that rewrites source
between test runs — every mutation check in this repo does exactly that.

**Nothing under `.harry/` is measured by coverage.** The tests copy capability folders into
a temporary directory and load them from there, so `coverage` sees no data for them. Dead
code in a capability does not show up in the gate, which is how `Slack.default_channel`
survived. Read capability code with that in mind.

### Patterns to reuse

- **`Connectors` in `src/harry/registry.py`** — a `dict` subclass whose `__missing__` says
  what was reached for and what was declared. Wherever a capability can ask for something
  that is not there, the refusal is what a person reads.
- **`check_exposure` in `scripts/check_capabilities.py`** — the namespace is what decides
  whose tool it is, so a tool composed from three connectors is nobody's to offer. Reuse
  that shape for any "who owns this" question between capabilities.
- **`WHAT_TO_DO` in `.harry/connectors/slack/connector.py`** — a service's error codes
  against the fix, a lookup table with the runbook beside it. `not_in_channel` is in it
  because inviting the bot is the step everybody skips.
- **`tests/fixtures/capabilities/tools/weather_nosy/`** — a capability that breaks the
  contract at registration rather than at call time, which is where a real one would.

## Links


- Decision: [[ADR-260913-210e08]] — A capability is handed the connectors it declared, and imports none of them

