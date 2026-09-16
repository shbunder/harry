---
id: STORY-260916-f048f5
title: Harry logs in to De Tijd from the NUC, measured before anything is built on it
feature: FEAT-260912-9c933f
status: Done
created: 2026-09-16
---

# STORY-260916-f048f5 — Harry logs in to De Tijd from the NUC, measured before anything is built on it

Part of [[FEAT-260912-9c933f]].

## Description

**Do this first.** Automated login is the riskiest thing in the feature, and every later
story assumes it works. A throwaway script, run from the `harry` image on the NUC with the
account in `.harry/connectors/tijd/.env.local`, answers it before any code is written.

If De Tijd's login service refuses a scripted login from the NUC, the feature stops here and
[[ADR-260916-b26785]] is revisited. Its option 1 — a person logging in through a remote view —
is the fallback.

The spike also records the page markers the connector will read. The 2026-09-16 measurement
only saw a reader who is not logged in.

## Acceptance criteria

- [x] A headed Chromium in the `harry` image logs in with the email and password, through both steps of `auth.mediafin.be`, and ends back on tijd.be
- [x] Which page markers change once logged in is recorded: `paywall-active` on `<html>`, the `.trck_sitenav_login` button, and anything better found
- [x] The measured article comes back through trafilatura with more than 1,000 characters logged in, against 263 logged out
- [x] The saved session, opened in a fresh browser, reads the article in full without logging in again
- [x] What a refused password looks like is recorded — the URL and the element carrying the message — without locking the account: one wrong attempt, at most
- [x] Whether a consent dialog has to be dismissed before the "Log in" button can be clicked is recorded
- [x] The findings are a dated note on FEAT-260912-9c933f, and nothing under `scratch/` is committed

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

