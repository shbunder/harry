---
id: STORY-260914-461f63
title: Harry can put a page on the tablet, and says so when it cannot
feature: FEAT-260912-74f222
status: Backlog
created: 2026-09-14
---

# STORY-260914-461f63 — Harry can put a page on the tablet, and says so when it cannot

Part of [[FEAT-260912-74f222]].

## Description

The connector: the credential, the client, the runbook, and the one write Harry does.

This is the folder the device token goes in, so it comes first — everything else in this
feature is on the other side of a credential that has nowhere to live until it exists.

The retry and the alert are here rather than in a later story because they are the whole
difference between a page that did not arrive and a page nobody knows did not arrive.

## Acceptance criteria

- [ ] A PDF is uploaded under the name it was given, inside the configured folder, and the answer says the folder and the id
- [ ] A folder that does not exist is created once at the top level; the next push finds it rather than making a second
- [ ] An upload that fails once is retried exactly once, and a successful retry puts nothing in Slack
- [ ] Two failed attempts raise, so the caller knows the page did not arrive
- [ ] Two failed attempts put one line in Slack naming the tablet and why, once per 24 hours
- [ ] A revoked token says so and says to re-pair, rather than reporting a network problem
- [ ] The device token appears in no log line, no exception message and no Slack message — asserted against a planted value
- [ ] With no DEVICE_TOKEN the connector is skipped saying which setting is missing, and every other capability still loads
- [ ] `make remarkable-pair CODE=…` exchanges the code once, writes the token to the gitignored .env.local, and prints that it worked without printing the token
- [ ] remarkapy is pinned to exactly 0.3.1 with the reason on the same line, and nothing requires a Go rmapi binary
- [ ] A live test pushes a real page to a real tablet, marked live and never in the gate
- [ ] docs/sources.md and the connector runbook say how to pair, what happens when a push fails, and what lands in Slack — by inspection: prose, and no automation can judge whether a re-pairing procedure reads clearly to somebody doing it at 07:00

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

