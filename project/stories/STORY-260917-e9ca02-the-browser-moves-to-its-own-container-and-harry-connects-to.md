---
id: STORY-260917-e9ca02
title: The browser moves to its own container, and Harry connects to it
feature: FEAT-260917-250f5a
status: Backlog
created: 2026-09-17
---

# STORY-260917-e9ca02 — The browser moves to its own container, and Harry connects to it

Part of [[FEAT-260917-250f5a]].

## Description

The browser moves out of Harry's container. A second service from the same image runs
`playwright run-server`; the tijd connector connects to it and states its launch options every
time. With no endpoint configured — a laptop, `make serve`, the live tests — the connector starts
a browser of its own exactly as it does today.

**The image has to change too:** the browsers are installed in root's cache today, which a
non-root user cannot read, so they move to a shared path.

Nothing about De Tijd's rules, waits or sentences changes. The only new failure is a browser
container that is not there, and that is the `browser` fault the connector already reports.

## Acceptance criteria

- [ ] The image installs its browsers where any user can read them, and the browser container runs as a non-root user with every capability dropped
- [ ] `docker-compose.yml` gains a browser service from the same image: no `.harry/` mount, no root `.env.local`, no data volume, no published port, and a test in the gate fails if it gains any of them
- [ ] The browser service is the only one with relaxed seccomp, and a test fails if the real or dev stack gains it
- [ ] The tijd connector takes an endpoint setting, connects when it is set, and starts its own browser when it is empty — both paths tested
- [ ] The launch options — headed, full Chromium, sandbox on — are stated on every connect, and a test fails if any of the three is dropped
- [ ] A browser container that cannot give a sandboxed browser is the existing `browser` fault: the summary prints, one Slack line, and no quiet fall back to an unsandboxed browser
- [ ] A browser container that is down costs De Tijd's text only, and VRT NWS and BBC News are read in the same Harry
- [ ] Through the running stack: a De Tijd article comes back with more than 1,000 characters, and the browser container's process is not root and asked for the sandbox (live)
- [ ] The saved session is still Harry's: read from `/data/tijd`, renewed, and never written inside the browser container (live)
- [ ] `.harry/connectors/tijd/CONNECTOR.md` and `docs/operating.md` say what the browser container is, what it is deliberately not given, and what a person sees when it is down

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

