---
id: FEAT-260912-8a0ab0
title: Harry starts with whatever is on disk, and one broken capability is skipped
track: full
created: 2026-09-12
touches: [core/loader, core/main, core/registry, core/sdk]
stories: [STORY-260913-b76fbd, STORY-260913-13a412, STORY-260913-c4f49d, STORY-260913-9c0de7]
decisions: [ADR-260912-399f07, ADR-260912-895441, ADR-260913-f38787]
---

# FEAT-260912-8a0ab0 — Harry starts with whatever is on disk, and one broken capability is skipped

## Summary

The core contract, and the property everything else rests on: a half-written capability is logged and stepped over rather than taking the process down. Without it the first thing you leave unfinished stops the morning page rendering at all, and you learn to develop somewhere else.

## Acceptance criteria

<!-- One box per scenario. These are what the pre-close-verifier builds its
     traceability matrix from. -->

- [x] A connector, a tool and a job in a capability root all load at start-up, and no file under src/harry/ names any of them in code
- [x] A capability that raises on import is logged and skipped, and every other one still loads
- [x] A declaration that does not parse is skipped with its parse error, not raised
- [x] A capability whose required config is absent disables itself, names the setting, and Harry still starts
- [x] GET /health lists which capabilities loaded and which were skipped, with the reason for each, and no secret in any field
- [x] A capability in a later root replaces an earlier one of the same name, reported in a WARNING and in /health
- [x] A capability under $HARRY_CAPABILITIES_DIR loads exactly as one in .harry/ does
- [x] A capability that imports anything under harry other than harry.sdk is skipped before its module runs, with a reason naming the import
- [x] register(registry, context) is the contract: registry exposes connector(), tool() and job(); context carries name, kind, folder, declaration, body, config, config_for() and log; a folder with no Python registers its declaration alone

## Stories

<!-- Maintained by `board.py new-story`. -->
- [x] [[STORY-260913-b76fbd]] — The SDK is the only thing a capability may import
- [x] [[STORY-260913-13a412]] — Capabilities are found, read and registered
- [x] [[STORY-260913-c4f49d]] — One broken capability costs exactly itself
- [x] [[STORY-260913-9c0de7]] — What loaded, what did not, and why

## Notes

<!-- Appended by `board.py note`. -->
- **2026-09-13** — plan-verifier: WARN, no BLOCK. Seven findings, all acted on before code. The three that changed the design: the criteria list now has one box per scenario (nine, not six); broken fixtures live under tests/fixtures/capabilities/ and load through a temporary root, because .harry/ is validated by make lint and a deliberately broken folder there would fail the gate forever; and scenario 9 now pins the contract — register(registry, context), three registry methods, the fields of Context — because every later feature is written against it. route, slack_action and on are deferred on purpose and Non-goals says so.
- **2026-09-13** — Reflection: pre-close-verifier returned REQUEST CHANGES — 1 Critical, 3 Important, 4 Suggestions, all acted on. Traceability 9/9 feature criteria and 18/18 story criteria, none marked by inspection. Degraded paths exercised: import raises, declaration does not parse, Python does not parse, required setting absent, connector absent, wrong kind registered, reach past the SDK, disabled, name mismatch, no declaration, shadowed, missing root, empty disk. Scope drift: Catalogue.of_kind() was built with no caller and removed rather than kept — the requirements page rejects route, slack_action and on for the same reason.

## Lessons Learned

### What worked

**A fixture that trips a wire, rather than a test that asserts an order.** The rule
"a forbidden import is refused *before* the module runs" is a claim about sequencing, and
sequencing is what an assertion on a reason string cannot check. So
`tests/fixtures/capabilities/connectors/nosy/connector.py` writes a marker file on the line
*above* its `import harry.scheduler`, and the test asserts the marker is absent. Same trick
in `connectors/disabled/`. Both survived the verifier's delete-it-and-see pass on the first
attempt, and almost nothing else that was written as an assertion did.

**A test that fails when a fixture folder is unused.**
`tests/test_loader_degrades.py::test_every_fixture_capability_is_used_by_a_test` fails if
any folder under `tests/fixtures/capabilities/` is not named by some test. It is four lines
and it removes a whole category of rot — a broken fixture nobody loads is a folder somebody
maintains for no reason.

**Running the thing.** `HARRY_LOG_LEVEL` configured uvicorn and nothing of Harry's, so
every line below WARNING was dropped. Nine scenarios, 219 tests and a green gate did not
find it; starting Harry with five capabilities and reading the terminal found it in ten
seconds. The setting *looked* applied, because uvicorn took the same value for its own
output and the skip warnings showed up regardless.

### What to do differently

**Ask "delete it, which test goes red?" while writing the control, not after.** The
pre-close verifier deleted every control in the diff one at a time and found six that
nothing tested — including the Context the loader builds, which is the contract every later
feature is written against. Blanking `name`, `kind` and `folder` left all 70 tests green.
They were "covered" in the coverage sense: every line ran. Nothing asserted the values.

**A control tested through a constructor is not tested.** `ContractError` was exercised by
building a `Registry` directly. Production only ever reaches it from inside
`loader._register`, and nothing checked that the refusal becomes a readable skip rather
than a traceback. The fix was one fixture that does it wrong and goes through `load()`.

**A guard's input set rots faster than the guard.** The check that core names no capability
walked the *fixtures* only. `.harry/` is empty today so it passed and looked right; the
first real connector would not have been covered, and nothing would have said so. Whenever
a guard iterates a roster, ask where the roster comes from and whether it grows with the
thing it is protecting.

**A fixture that is deliberately broken breaks the linters too.** `tests/fixtures` had to
be excluded from both ruff and pyright before a capability whose Python does not parse could
be committed. Worth deciding on the first fixture rather than the twelfth.

### Patterns to reuse

- **`src/harry/declaration.py`** — one definition of the `.harry/` format, imported by both
  `harry.loader` and `scripts/check_capabilities.py`. Same move as `config.env_key`. Two
  readers of one format drift, and they drift by the gate passing something the loader
  refuses at 06:30.
- **`src/harry/loader.py:_redact`** — every value a capability declared `secret: true` is
  scrubbed from any reason before it reaches `/health` or the log. The test asserts the
  secret is absent *and* that `[redacted]` is present, so a capability that failed earlier
  than expected cannot produce a false pass. Copy that second assertion anywhere a
  negative is being checked.
- **`tests/fixtures/capabilities/connectors/introspect/`** — a capability that registers its
  own `Context`, so a test can inspect what the loader actually built rather than one it
  wrote itself. Reuse for anything that hands an object to third-party code.
- **`tests/test_loader.py::capability_names`** — a roster built from every capability root
  plus the fixtures, so the no-naming guard grows with the tree.
- **`docs/capabilities.md`** — the table of "what is wrong" against "the reason you get" is
  the shape worth repeating for any component with many failure modes. It is the page
  somebody reads at 07:00.

## Links

- Requirements: [[FEAT-260912-8a0ab0]]
- [[ADR-260912-399f07]] — capabilities are folders under `.harry/`
- [[ADR-260912-895441]] — a capability's settings live in its own folder
- [[ADR-260913-f38787]] — the roots list and the principal
