---
id: FEAT-260917-250f5a
title: Harry's browser runs as an unprivileged user with Chromium's sandbox on
track: full
created: 2026-09-17
touches: [Dockerfile, compose, connectors/tijd, docs/operating]
stories: []
decisions: []
---

# FEAT-260917-250f5a — Harry's browser runs as an unprivileged user with Chromium's sandbox on

## Summary

Harry reads De Tijd in a headed Chromium, and today that browser renders De Tijd's pages — and
the advertising scripts on them — **as root, without Chromium's sandbox**, in the container that
can read every credential Harry holds: each connector's `.env.local` through the `/settings`
mount (the tablet token, the iCloud and Slack credentials, the De Tijd password), the root
`.env.local` with the MCP bearer token, and the saved De Tijd session on `/data`. One exploit in
the renderer would reach all of them. The owner accepted that risk on 2026-09-17 to get De Tijd
running, on condition this follows.

What is known, so this starts from facts rather than a guess:

- **A non-root user alone does not turn the sandbox on.** Playwright 1.62 passes `--no-sandbox`
  unless `launch(chromium_sandbox=True)` is given.
- **Docker's default seccomp profile usually blocks what the sandbox needs.** Playwright's own
  guidance for Docker is a seccomp profile that allows it, or running as a non-root user with
  one. Measure it on the NUC before choosing.
- **The container's user owns what it writes.** `harry-data` holds files written by root today;
  a non-root user needs that volume's ownership changed, once, without losing the store.
- **Chromium's patch level follows the locked Playwright version.** A browser fix arrives only on
  a relock and a rebuild, so that belongs in the runbook.
- **Reducing what the renderer can reach is a second, separate lever:** the credentials the
  browser process could read, and the third-party requests a page may make — the latter measured
  against De Tijd's bot filter first, which refuses anything that does not look like a browser.

Decided in [[ADR-260916-b26785]], where the accepted risk is recorded.

## Acceptance criteria

<!-- One box per scenario. These are what the pre-close-verifier builds its
     traceability matrix from. -->

- [ ] <criterion>

## Stories

<!-- Maintained by `board.py new-story`. -->

## Notes

<!-- Appended by `board.py note`. -->

## Links

- Requirements: [[FEAT-260917-250f5a]]
