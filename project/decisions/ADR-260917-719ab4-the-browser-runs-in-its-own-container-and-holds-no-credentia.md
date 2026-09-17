---
id: ADR-260917-719ab4
title: The browser runs in its own container, and holds no credential
status: Accepted
created: 2026-09-17
feature: FEAT-260917-250f5a
supersedes: ''
superseded_by: ''
---

# ADR-260917-719ab4 — The browser runs in its own container, and holds no credential

## Status

Accepted

Drives [[FEAT-260917-250f5a]].

## Context & problem

Harry reads De Tijd in a headed Chromium that renders a commercial news site — its advertising
and tracking scripts included. Since 2026-09-17 that browser runs in the container that can read
every credential Harry holds, as root, with Chromium's sandbox off. [[ADR-260916-b26785]] records
that as an accepted risk with this as its condition.

Measured the same day, from `harry:6220e5c` on the NUC:

- Non-root works, and De Tijd still answers 200 — once the browsers are installed somewhere a
  non-root user can read, rather than in root's cache.
- **`chromium_sandbox=True` will not launch under Docker's default seccomp profile.** It starts
  with `seccomp=unconfined` or with `SYS_ADMIN`, and neither is something to hand a container
  that holds credentials.
- The chrome seccomp profile everyone links to is **too old for runc 29.1.3**: the container will
  not start at all with it. Nobody here is going to maintain a 36 KB syscall list.
- `playwright run-server` in one container, driven by `chromium.connect()` from another, gives a
  headed sandboxed browser, De Tijd answers 200, and the session's cookies come back to the
  caller. The calling container has no `/settings`.

So the sandbox is only available on terms that weaken the container it runs in. That settles
which container it should be.

## Decision drivers

- **Bounded** — what a compromised renderer can reach matters more than how hard it is to reach it
- Nothing that needs a third-party file nobody maintains
- De Tijd must read exactly as it does today: headed, 200, whole articles
- A laptop with no extra container still has to work

## Considered options

### Option 1: Keep one container; add a non-root user and the sandbox

**For:** no new service. One Dockerfile change and one launch argument.
**Against:** the sandbox needs `seccomp=unconfined` or `SYS_ADMIN` **on the container that mounts
every credential** — trading a container-level mitigation for a browser-level one, on the box
where the prize is. And an escaped renderer still runs as the user that must be able to read
those files, because Harry reads them at start-up.

### Option 2: One container, but launch the browser as a second user

A wrapper at `executablePath` that `setpriv`s down to a user with no read access to the mounted
files.

**For:** no new service, and credentials out of the renderer's reach.
**Against:** Playwright creates the browser's profile directory as *its own* user, mode 700, so
the browser's user cannot write it; working around that means widening permissions on a directory
the browser controls. Harry would also have to stay root to drop privileges at all.

### Option 3: The browser gets its own container, with nothing in it

`playwright run-server` from the same image, on the compose network only, no credential mount, no
data volume, non-root, every capability dropped, and `seccomp=unconfined` scoped to it so
Chromium's own sandbox can run. Harry connects with `chromium.connect()` and passes the launch
options in the URL.

**For:** an exploited renderer lands in a container holding nothing — no credentials, no store, no
published port. The relaxed seccomp applies only there. Measured end to end today.
**Against:** a second service to run and to watch. Client and server must be the same Playwright
version — true by construction, since both are this one image, except during a deploy while one
container has restarted and the other has not. The session's cookies travel over the compose
network to the browser, which is what a browser is for, but they do leave Harry's process.

## Decision outcome

**Option 3. The browser runs in its own container and holds no credential.** **Bounded** drove
it: the sandbox is worth having, and it is only available on terms that would weaken the
container holding the credentials — so the browser moves to a container where those terms cost
nothing.

The tijd connector connects to `ws://harry-browser:3000/` and states its launch options every
time: headed, full Chromium, sandbox on. A browser container that cannot give that is a failure
Harry reports, never a quiet fall back to an unsandboxed browser.

**With no endpoint configured, the connector starts a browser of its own, as it does today.**
That is what a laptop does, and what the live tests do, so the code that drives a browser stays
under test on a machine with one container.

## Consequences

**Good:**

- A renderer exploit on a De Tijd page reaches a container with no credentials, no store and no
  way out to the network's inside.
- Chromium's sandbox is on, and its cost — relaxed syscall filtering — is paid where there is
  nothing to take.
- Harry's own container stops running a browser at all, which makes its own user a smaller
  question, to be settled on its own.

**Bad:**

- **A second service to keep alive.** When it is down, De Tijd's stories print their summaries
  and Slack says the browser could not start; nothing else changes.
- **Two containers from one image must both be restarted on a deploy.** In the seconds between,
  a Playwright version mismatch is possible, and it reads as a browser that could not start.
- **The session leaves Harry's process.** The cookies are handed to the browser container to use,
  as any browser must have them. They are never written to disk there.
- **`seccomp=unconfined` on that container** is a real relaxation, justified only by its being
  empty. Anything added to that container later has to revisit this record.
