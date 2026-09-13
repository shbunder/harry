---
id: FEAT-260912-8a0ab0
title: Harry starts with whatever is on disk, and one broken capability is skipped
track: full
created: 2026-09-12
touches: [core/loader, core/main, core/registry, core/sdk]
stories: [STORY-260913-b76fbd, STORY-260913-13a412, STORY-260913-c4f49d, STORY-260913-9c0de7]
decisions: []
---

# FEAT-260912-8a0ab0 — Harry starts with whatever is on disk, and one broken capability is skipped

## Summary

The core contract, and the property everything else rests on: a half-written capability is logged and stepped over rather than taking the process down. Without it the first thing you leave unfinished stops the morning page rendering at all, and you learn to develop somewhere else.

## Acceptance criteria

<!-- One box per scenario. These are what the pre-close-verifier builds its
     traceability matrix from. -->

- [ ] A connector, a tool and a job under .harry/ all load at start-up without core naming any of them
- [ ] A capability that raises on import is logged and skipped, and every other one still loads
- [ ] A capability whose required config is absent disables itself, says so, and Harry still starts
- [ ] A capability's setting is read from HARRY_<IMPLEMENTATION>_<SETTING>, falling back to its declared default
- [ ] GET /health lists which capabilities loaded and which were skipped, with the reason for each
- [ ] A capability under $HARRY_CAPABILITIES_DIR loads exactly as one in .harry/ does

## Stories

<!-- Maintained by `board.py new-story`. -->
- [ ] [[STORY-260913-b76fbd]] — The SDK is the only thing a capability may import
- [ ] [[STORY-260913-13a412]] — Capabilities are found, read and registered
- [ ] [[STORY-260913-c4f49d]] — One broken capability costs exactly itself
- [ ] [[STORY-260913-9c0de7]] — What loaded, what did not, and why

## Notes

<!-- Appended by `board.py note`. -->

## Links

- Requirements: [[FEAT-260912-8a0ab0]]
