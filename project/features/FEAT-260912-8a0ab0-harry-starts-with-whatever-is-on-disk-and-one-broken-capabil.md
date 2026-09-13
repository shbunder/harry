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

- [ ] A connector, a tool and a job in a capability root all load at start-up, and `git grep -n <name> -- src/harry/` finds nothing
- [ ] A capability that raises on import is logged and skipped, and every other one still loads
- [ ] A declaration that does not parse is skipped with its parse error, not raised
- [ ] A capability whose required config is absent disables itself, names the setting, and Harry still starts
- [ ] GET /health lists which capabilities loaded and which were skipped, with the reason for each, and no secret in any field
- [ ] A capability in a later root replaces an earlier one of the same name, reported in a WARNING and in /health
- [ ] A capability under $HARRY_CAPABILITIES_DIR loads exactly as one in .harry/ does
- [ ] A capability that imports anything under harry other than harry.sdk is skipped before its module runs, with a reason naming the import
- [ ] register(registry, context) is the contract: registry exposes connector(), tool() and job(); context carries name, kind, folder, declaration, body, config, config_for() and log; a folder with no Python registers its declaration alone

## Stories

<!-- Maintained by `board.py new-story`. -->
- [ ] [[STORY-260913-b76fbd]] — The SDK is the only thing a capability may import
- [ ] [[STORY-260913-13a412]] — Capabilities are found, read and registered
- [ ] [[STORY-260913-c4f49d]] — One broken capability costs exactly itself
- [ ] [[STORY-260913-9c0de7]] — What loaded, what did not, and why

## Notes

<!-- Appended by `board.py note`. -->
- **2026-09-13** — plan-verifier: WARN, no BLOCK. Seven findings, all acted on before code. The three that changed the design: the criteria list now has one box per scenario (nine, not six); broken fixtures live under tests/fixtures/capabilities/ and load through a temporary root, because .harry/ is validated by make lint and a deliberately broken folder there would fail the gate forever; and scenario 9 now pins the contract — register(registry, context), three registry methods, the fields of Context — because every later feature is written against it. route, slack_action and on are deferred on purpose and Non-goals says so.

## Links

- Requirements: [[FEAT-260912-8a0ab0]]
- [[ADR-260912-399f07]] — capabilities are folders under `.harry/`
- [[ADR-260912-895441]] — a capability's settings live in its own folder
- [[ADR-260913-f38787]] — the roots list and the principal
