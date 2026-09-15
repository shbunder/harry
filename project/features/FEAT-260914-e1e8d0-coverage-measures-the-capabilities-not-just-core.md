---
id: FEAT-260914-e1e8d0
title: Coverage measures the capabilities, not just core
track: story
created: 2026-09-14
touches: [core, scripts]
stories: [STORY-260914-2195f2]
decisions: []
---

# FEAT-260914-e1e8d0 — Coverage measures the capabilities, not just core

## Summary

Coverage reports 94% and measures none of `.harry/`. `pyproject.toml` lists `.harry` under
`[tool.coverage.run] source`, but `coverage report --include=".harry/*"` says "No data to
report" — the loader imports each capability from a copied temporary directory, so nothing
is ever attributed back to the file on disk.

Every connector and every tool is therefore outside the floor. The reMarkable connector is
261 lines that contribute nothing to the percentage and cannot trip `fail_under`, and two
security controls in it were untested for exactly that reason: the line that keeps a device
token out of `~/.rmapi`, and the line that sets the timeout the Slack message quotes. Both
were found by a person reading, which is the thing the number is supposed to reduce.

The entry in `source` is a list nothing executes — the defect `.claude/rules/inert-controls.md`
names, in the file that enforces it.

## Acceptance criteria

- [ ] `coverage report` lists at least one file under `.harry/`, so the capabilities are inside the number
- [ ] Deleting a tested branch from `.harry/connectors/weather/connector.py` moves the reported percentage
- [ ] The floor still passes, or the floor is raised deliberately in the same change — never lowered
- [ ] A test asserts that the measured set is non-empty for `.harry/`, so this cannot silently stop working again
- [ ] `docs/` says what the number covers and what it does not

## Stories

<!-- Maintained by `board.py new-story`. -->
- [ ] [[STORY-260914-2195f2]] — Coverage sees the capability files the loader ran

## Notes

- **2026-09-15** — measured while building the morning page, and it is worse than "coverage does not see `.harry/`". The path *was* in `[tool.coverage.run] source`. It measured nothing, because a capability test copies its folder into a temporary root and loads the copy — so the executed file is `/tmp/.../connectors/icloud/connector.py` and none of it is attributed back to `.harry/connectors/icloud/`. Every capability read as **fully covered** and `skip_covered` hid it. Then `tests/test_morning_page_job.py` loaded the real tree by path, five connectors were suddenly measured through one code path each, and the total fell from 92% to 69% — a floor that moves twenty points on which test ran. `.harry` is out of `source` for now, with the reason written there. The lead worth following: `[tool.coverage.paths]` aliasing, which is exactly the mechanism for "these two paths are the same file", applied by `coverage combine` between the run and the report.

<!-- Appended by `board.py note`. -->

## Links

