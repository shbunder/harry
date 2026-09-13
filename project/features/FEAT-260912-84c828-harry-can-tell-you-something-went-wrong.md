---
id: FEAT-260912-84c828
title: Harry can tell you something went wrong
track: full
created: 2026-09-12
touches: [connectors/slack, core/alerts, core/main, core/registry, core/loader]
stories: [STORY-260913-1f320c, STORY-260913-e6f9b4, STORY-260913-bb45b7]
decisions: [ADR-260912-399f07, ADR-260912-895441, ADR-260913-816553]
---

# FEAT-260912-84c828 — Harry can tell you something went wrong

## Summary

One-way messages into Slack, which every other feature depends on. Alerting is a core principle and it cannot wait for the Slack loop in a later phase: a degraded source, a lapsed credential and a failed push all need somewhere to arrive from the first morning.

## Acceptance criteria

<!-- One box per scenario. These are what the pre-close-verifier builds its
     traceability matrix from. -->

- [x] An alert reaches Slack as one chat.postMessage carrying the channel and the caller's text, with nothing added
- [x] Core raises an alert without naming any capability, and a connector that registered itself receives it
- [x] With nothing registered, an alert is a WARNING in the log and nothing raises
- [x] An alert carrying a key is not sent again within 24 hours; one with no key is always sent
- [x] Slack being unreachable, answering 500, or not answering at all costs the message after 5 seconds, is logged, and does not break the caller
- [x] A capability skipped at start-up produces one alert naming it, its kind and the reason, with its own declared secrets taken out; one that loaded produces none
- [x] The bot token appears in no log line, no alert and no /health field, and .harry/connectors/slack/.env leaves it empty
- [x] `make lint` passes on the first real capability in .harry/ — the declaration validates and its generated .env matches the schema

## Stories

<!-- Maintained by `board.py new-story`. -->
- [x] [[STORY-260913-1f320c]] — An alert reaches Slack, and nothing about it names Slack in core
- [x] [[STORY-260913-e6f9b4]] — The same fault does not tell you twice today
- [x] [[STORY-260913-bb45b7]] — A capability that did not load reaches a person

## Notes

<!-- Appended by `board.py note`. -->
- **2026-09-13** — Inherits a case from FEAT-260912-8a0ab0: a capability skipped at start-up reaches nobody today. /health carries it, and nothing watches /health. A capability skipped three weeks ago looks exactly like one that was never installed.
- **2026-09-13** — Reflection: pre-close-verifier returned REQUEST CHANGES — 1 Critical, 2 Important, 4 Suggestions, all acted on. Traceability 8/8 feature criteria and 17/17 story criteria, none by inspection. Degraded paths exercised: no credential, a revoked token (invalid_auth), a bot never invited (not_in_channel), a wrong channel, a 502 that is not JSON, a refused connection, a read timeout, a sink that raises, a fault nobody heard, and a capability that was replaced rather than broken. Scope drift: the plural wording of a missing-settings message was improved outside any criterion, and slack-bolt was dropped as a dependency this feature made dead. Not verified: that a message lands in a real Slack workspace — no credential on this machine. The live test for it is tests/test_slack_connector.py::test_a_message_really_arrives_in_a_real_workspace, run with make test-live.

## Lessons Learned

### What worked

**Reordering the queue when a criterion pointed at something that did not exist.** The
scheduler was next, and its headline criterion is "puts one message in Slack". Building it
first would have meant either an alert path nothing delivers or a criterion quietly
reworded. This feature's own summary already said it — "which every other feature depends
on" — and reading that before starting cost nothing.

**A fixture capability that writes to a file.** A test that starts the real app cannot see
into the module the loader imported: different namespace, no shared object.
`tests/fixtures/capabilities/connectors/listener/` appends every alert it is handed to a
file beside itself, and the file is the only thing both ends share. That is what made the
one test through `build_app()` possible.

**Asking what a failed delivery means.** `test_a_fault_nobody_heard_is_not_remembered` came
out of one question while writing the suppression: if Slack was down, was the fault
reported? Recording the key anyway would have suppressed the retry for a day and the fault
would never have been heard at all — a bug whose only symptom is silence. Four lines of
code and the most valuable test in the feature.

**Running it.** The start-up alert printed `required settings bot_token, channel is not
set`. Which is not a sentence, and is one a person reads on a phone.

### What to do differently

**A test one layer beneath the real caller cannot notice the real caller being removed.**
Every alerting test called `report_start_up()` directly. Neutralising the call inside
`build_app()` — its only caller in production — left all 293 tests passing. The verifier
found it by mutation, not by reading. **Ask of every new code path: which test calls this
the way production does?**

**A number that matches the library default is not a tested number.** The five-second Slack
ceiling was asserted against the resolved request, and httpx's default is also five
seconds, so a call with no `timeout=` produced byte-identical extensions. The assertion
recorded a belief. Assert the argument the code chose, not the value that came out.

**A dependency declared for a feature that does not exist is rent.** `slack-bolt` was in
`pyproject.toml` for Socket Mode. This feature's Non-goals rule out Socket Mode and the
connector explains in its own docstring why it is not used — so the dependency installed on
every machine and nothing reached it. Dropped.

**Write the ADR when the contract changes, not after.** `registry.alerts()` went into the
requirements page as "the fourth registry method" with no decision record, contradicting
`CLAUDE.md` and the loader's own scenario 9. Three documents would have disagreed the day
it shipped. The fix — kinds against roles — is a better design than what was there, and it
came out of being made to write it down.

### Patterns to reuse

- **`src/harry/alerts.py`** — core reports a fault and holds a list of functions. The
  registry method is a **role** rather than a kind, so a connector registers a client and a
  sink and neither refuses the other. Reuse the shape for the next thing a capability can
  additionally *do*.
- **`Alerts._deliver` returning whether anybody took it** — the difference between "quiet
  because it was already reported" and "quiet because nobody was listening". Any suppression
  or caching layer needs the same distinction, and it is invisible without it.
- **`tests/fixtures/capabilities/connectors/listener/`** — a capability that records what it
  was given, for any test that has to observe behaviour across the loader's import boundary.
- **`.harry/connectors/slack/CONNECTOR.md`** — the runbook shape: a table of what the
  service says against what to do about it, beside the code rather than in a page somebody
  has to remember exists. `not_in_channel` is in it because inviting the bot is the step
  everybody skips.
- **`tests/test_slack_connector.py`** — copies the real `.harry/` folder into a temporary
  root and loads it, rather than importing it. `pyproject.toml` keeps `.harry` off pytest's
  path on purpose, so the declaration, the generated `.env`, the config resolution and the
  registration are all under test together.

## Links

- Requirements: [[FEAT-260912-84c828]]
- [[ADR-260912-399f07]] — capabilities are folders under `.harry/`
- [[ADR-260912-895441]] — a capability's settings live in its own folder
- Decision: [[ADR-260913-816553]] — A capability can be somewhere alerts go, and says so in code

