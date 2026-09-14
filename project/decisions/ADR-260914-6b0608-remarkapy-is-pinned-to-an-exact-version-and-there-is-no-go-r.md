---
id: ADR-260914-6b0608
title: remarkapy is pinned to an exact version, and there is no Go rmapi binary
status: Accepted
created: 2026-09-14
feature: FEAT-260912-74f222
supersedes: ''
superseded_by: ''
---

# ADR-260914-6b0608 — remarkapy is pinned to an exact version, and there is no Go rmapi binary

## Status

Accepted

Drives [[FEAT-260912-74f222]].

## Context & problem

reMarkable publishes no API. Every client that talks to the cloud — `rmapi`, `rmapy`, `rmcl`,
`remarkapy` — was written by reading traffic. reMarkable changes the protocol when it suits
them and tells nobody, and in **August 2026 a change broke every write** until the clients
were patched. Two of those four clients are archived and dead.

So the question is not which client is nicest. It is: when the protocol moves, how does Harry
find out, and how bad is the morning it finds out?

A loose pin — `remarkapy>=0.2`, which is what `pyproject.toml` says today — answers that
badly. A container rebuilt on a Tuesday picks up whatever the newest release is, including
the one that broke every write. The failure arrives at 06:30 on a morning nobody changed
anything, which is the hardest kind to diagnose.

There is a second question underneath. The plan assumed pairing needed the Go `rmapi` binary:
`rmapi` has an interactive pairing flow and the Python clients were believed not to. That
would have put a Go toolchain or a downloaded binary into the container, for one call made
once per machine.

## Decision drivers

- **Bounded.** The device token is complete read and write over every document on the tablet,
  with no scopes. Whatever runs with it should be as small and as known as possible.
- **Alerting.** A protocol break has to arrive as a failed push with a message, on a morning
  somebody can connect it to a deploy — not as a silent behaviour change.
- **Explainable.** Somebody debugging a failed push in six months needs to know which version
  worked, and why that number and not a range.
- Reproducibility. The NUC's container and this laptop must run the same client, or a failure
  here proves nothing about there.

## Considered options

### Option 1: `remarkapy==0.3.1` exactly, and no `rmapi`

**For:** The container and the laptop run byte-identical client code, so a failure reproduces.
A protocol break arrives when *somebody deliberately moves the pin*, on a day they are looking
at it, rather than on the next rebuild. The spike measured that 0.3.1 pairs, uploads a PDF and
**that PDF appeared on the device** — so the pin is on a version known to work end to end,
not on the newest one. `register_device(code)` removes the reason `rmapi` was in the plan,
which takes a Go binary out of the image.

**Against:** Harry does not get a protocol fix automatically. The morning after reMarkable
changes something, the push fails here and stays failing until somebody bumps the pin — where
a range might have healed itself. Somebody has to watch the project.

### Option 2: `remarkapy>=0.3,<0.4`, a compatible range

**For:** Patch releases arrive on their own, which is the usual and usually right answer. When
reMarkable breaks the protocol, the fix reaches Harry on the next rebuild with nobody paged.
Semantic versioning exists precisely so a caller can say "I accept fixes, not changes".

**Against:** It assumes the version number means something, and for a reverse-engineered
client it cannot. A release that restores writes against a changed protocol is not a patch —
it is a different protocol wearing a patch number, because the thing it is compatible with is
a service, not a specification. The August 2026 break went out under a version bump that
looked safe. And the healing is only a benefit if the fix arrives *before* the break: in
practice the break arrives first and the range delivers it faster.

### Option 3: Keep the Go `rmapi` binary as a fallback pusher

**For:** Two independent clients means one can be tried when the other fails, and `rmapi` is
the most-used and fastest-patched of the four.

**Against:** Two clients is two protocol implementations to keep working, a Go toolchain or a
pinned binary download in the image, and a fallback path that would be exercised roughly never
— which `.claude/rules/inert-controls.md` says is a path that does not work. It also doubles
the surface holding a token that can rewrite the whole tablet. Worth revisiting only if
remarkapy is actually abandoned; `rmapy` and `rmcl` already were.

## Decision outcome

**Harry depends on `remarkapy==0.3.1` and nothing else reaches the tablet. There is no Go
`rmapi` binary, in the image or on the path.**

The pin carries its reason on the same line, so nobody widens it while tidying:

```toml
"remarkapy==0.3.1",   # EXACT. Reverse-engineered protocol: a release broke every write in
                      # August 2026. 0.3.1 is the version the spike paired and pushed with,
                      # confirmed on the device. Move it deliberately, and push a real page after.
```

**Moving the pin is a change with a test attached**: `make test-live ARGS=tests/test_remarkable_connector.py` pushes a real page to a real tablet, and it is the only thing that can tell you the new version still works. That command is the reason a version bump is a ten-minute job rather than a gamble.

The core principle is **Bounded**: the decision is about what runs holding a token that can rewrite every document on the device.

## Consequences

**What this makes harder.** Harry is now somebody's job once or twice a year. When reMarkable
changes the protocol, the push fails and keeps failing until a person bumps `0.3.1` to
whatever fixed it and runs the live test. A range would have done that unattended — badly,
and at a moment of its choosing, but unattended. The Slack line on the second failed push is
what makes this survivable rather than silent, which is why that line is in the same feature
and not a later one.

There is no fallback pusher. If remarkapy is abandoned the way `rmapy` and `rmcl` were, this
connector is rewritten against another client rather than switched to one.

**What it makes easier.** A failed push is one of two things — the token, or the protocol —
and the pinned version means "it worked last week and nothing here changed" is a true
statement rather than a hope. The container has no Go in it. And the image builds the same
today as it did in September, which is what makes a NUC deployment reproducible at all.
