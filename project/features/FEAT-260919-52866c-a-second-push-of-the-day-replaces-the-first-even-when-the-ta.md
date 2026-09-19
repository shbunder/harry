---
id: FEAT-260919-52866c
title: A second push of the day replaces the first, even when the tablet has changed since
track: story
created: 2026-09-19
touches: [connectors/remarkable]
stories: [STORY-260919-8c5576]
decisions: []
---

# FEAT-260919-52866c — A second push of the day replaces the first, even when the tablet has changed since

## Summary

On 2026-09-19 the tablet ended the day with two documents called `2026-09-19` in `🗞️ Daily`.
The page was built at 08:08 and again at 10:39, and the second push reported `replaced: 0` —
it found nothing to replace. Nothing was logged and nothing reached Slack, because nothing
failed: the removal was never attempted.

**Measured afterwards, read-only, with a fresh client asking the tablet directly:** one
`🗞️ Daily` folder, both copies in it — `690bcfef` from 08:08 and `0134bb70` from 10:39. So the
08:08 copy was on the tablet the whole time, and the listing Harry trusted at 10:39 did not
include it.

Harry holds one remarkapy client for the life of the process, and remarkapy answers from the
state it remembers unless a call passes `refresh=True`. Harry never does. Between the two
pushes the tablet changed on its own — most likely the page being opened, which syncs the
reading position — so the remembered state was out of date when the second push went looking
for what it replaced.

**This is the fix FEAT-260915-bbbab1 wrote and reverted.** Its first theory was a stale
listing, fixed with `refresh=`; the live test passed against the unfixed connector too, because
it built a fresh client every time and a fresh client is never stale. That was the right call
on the evidence then. This time there is a real morning, and the gate test can be written to
fail without the fix: a stand-in whose unrefreshed listing lags behind the tablet.

## Acceptance criteria

<!-- One box per scenario. These are what the pre-close-verifier builds its
     traceability matrix from. -->

- [x] The removal after a push lists the folder with `refresh=True`, so it sees what is on the tablet rather than what the client remembers
- [x] A gate test with a stand-in whose unrefreshed listing lags behind the tablet fails without the fix and passes with it
- [x] `docs/` and the connector's runbook no longer say a duplicate means the removal was refused twice — it can also mean the listing was out of date, which the fix removes
- [ ] `by inspection: it is the owner's tablet` — the older `2026-09-19` is sent to the tablet's trash, once the owner has agreed

## Stories

<!-- Maintained by `board.py new-story`. -->
- [x] [[STORY-260919-8c5576]] — The removal after a push asks the tablet, not the client's memory

## Notes

<!-- Appended by `board.py note`. -->

## Links

