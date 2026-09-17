---
id: FEAT-260917-250f5a
title: Harry's browser runs in its own container, with no credential to steal
track: full
created: 2026-09-17
touches: [Dockerfile, compose, connectors/tijd, docs/operating, docs/sources]
stories: [STORY-260917-2441de, STORY-260917-e9ca02]
decisions: [ADR-260917-719ab4]
---

# FEAT-260917-250f5a — Harry's browser runs in its own container, with no credential to steal

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
- **Asking for the sandbox over a connection is not the same as getting it.** `playwright
  run-server` drops `chromiumSandbox` from the connect URL unless it was started with `--unsafe`,
  and reports nothing. Check the running processes, never the request.
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

- [x] The browser container mounts no `.harry/`, no root `.env.local` and no data volume, and is handed no credential
- [x] It runs as a non-root user, with Chromium's sandbox on and every Linux capability dropped
- [ ] De Tijd reads as before through it: headed, 200, the whole article, and the session on Harry's volume renewed
- [x] The launch options are stated on every connect — without them the browser is headless and De Tijd answers 403
- [x] A machine with no browser container still reads De Tijd by starting a browser of its own
- [x] A browser container that is down or unsandboxed costs De Tijd's text only, says so once in Slack, and never falls back to an unsandboxed browser
- [x] The relaxed seccomp is on the browser container alone, and a test fails if either Harry stack gains it

## Stories

<!-- Maintained by `board.py new-story`. -->
- [ ] [[STORY-260917-2441de]] — What a sandboxed browser needs in Docker, measured before anything is built on it
- [ ] [[STORY-260917-e9ca02]] — The browser moves to its own container, and Harry connects to it

## Notes

<!-- Appended by `board.py note`. -->
- **2026-09-17** — The browser container is built and proven without an account: a live test stands one up — unprivileged, capabilities dropped, seccomp relaxed — and drives it with the connector's own Chromium wrapper. De Tijd's public homepage answers 200 through it, and the container has no /settings. 13 mutations of the new controls each go red. The two live tests that need the De Tijd account skip in this worktree, because the account lives in the main checkout; they run from there after the merge, with the deploy.
- **2026-09-17** — The sandbox was off, and the test that said otherwise could not have found out. It asked the image for `ps`, which is not installed, and asserted `--no-sandbox` was absent from the empty string that came back. The cause underneath: `playwright run-server` discards the `chromiumSandbox` the connect URL asks for unless the server was started with `--unsafe`, and says nothing. Measured on the shipped flags: without `--unsafe`, most Chromium processes run with `--no-sandbox`; with it, none do. `--unsafe` is now in the browser service's command, and the test holds a page open and reads the container's `/proc` — so what is checked is what is running, not what was requested.

## Links

- Requirements: [[FEAT-260917-250f5a]]
- Decision: [[ADR-260917-719ab4]] — The browser runs in its own container, and holds no credential

