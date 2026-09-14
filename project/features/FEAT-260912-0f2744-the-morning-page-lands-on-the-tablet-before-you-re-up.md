---
id: FEAT-260912-0f2744
title: The morning page lands on the tablet before you're up
track: full
created: 2026-09-12
touches: [core/registry, core/loader, jobs/morning-page, tools/digest, scripts]
stories: [STORY-260914-397bbd, STORY-260914-abef7c, STORY-260914-46e9e7]
decisions: [ADR-260913-c477cd, ADR-260913-210e08, ADR-260912-b22e46, ADR-260912-bd36c2]
---

# FEAT-260912-0f2744 — The morning page lands on the tablet before you're up

## Summary

What all of it is for. At 06:30 a Claude scheduled task asks Harry for candidates, decides what matters, writes a short intro and asks for the page. Harry fetches the chosen articles, renders the PDF and pushes it. Not headlines: the full articles, as pages behind the front page.

## Acceptance criteria

<!-- One box per scenario. These are what the pre-close-verifier builds its
     traceability matrix from. -->

- [ ] A capability may declare a connector `optional:` — handed over when it loaded, absent when it did not, and the capability still loads
- [ ] `requires:` still refuses a capability whose connector is missing, and `make lint` refuses an `optional:` naming a connector that does not exist
- [ ] digest_list_candidates calls weather.today(), calendar.today() and news.candidates(limit) and returns their answers, and returns the same shape with no sources loaded at all
- [ ] Candidates come back newest first, capped at limit, and a capped answer says how many were dropped; summary is the source's own text, truncated at 280 characters under concise
- [ ] A source that raises, and a source that returns None, both leave that section reading "unavailable" rather than blank, with the others intact
- [ ] digest_build takes an intro and picks of id-and-note, and the front page carries the intro verbatim
- [ ] Each picked article appears with the note Claude wrote above its text, unedited
- [ ] An article whose text could not be fetched still appears with its headline and note, saying the text was unavailable
- [ ] digest_build resolves each pick with news.article(id), so nothing is held between the two calls, and an id the source does not know is an error naming it
- [ ] picks is capped at 12, and digest_build emits a progress notification per article so the call survives past 300 seconds
- [ ] The page renders at exactly 509.34 by 679.13 points, with an outline entry per article in the order Claude picked
- [ ] With no tablet the page is written to out_dir/<date>.pdf and the answer quotes the path; with one, tablet.push is called and the answer quotes what it returned, and the page stays on disk
- [ ] The morning-page job is one markdown file whose brief is served as a prompt and tells Claude the three calls to make
- [ ] `make digest-dry` renders to out/digest.pdf through scripts/call_tool.py with no server, credential or tablet, and prints what it could not put on the page
- [ ] `make digest-now` is removed — it names a module that never existed, and pushing is another feature's
- [ ] Both digest tools are always_load, because a tool-search round trip at 06:30 is a failure mode with no upside

## Stories

<!-- Maintained by `board.py new-story`. -->
- [ ] [[STORY-260914-397bbd]] — A capability can declare a connector optional and still load without it
- [ ] [[STORY-260914-abef7c]] — Claude can see what today could contain, and pick from it
- [ ] [[STORY-260914-46e9e7]] — The page carries what Claude chose and what Claude wrote about it

## Notes

<!-- Appended by `board.py note`. -->
- **2026-09-14** — 2026-09-14: returned to Backlog before any code, on Shaun's re-sequencing — sources first, then the page. The plan stays and is the more valuable half: the five source signatures the page will call are written down, so weather, calendar, news, De Tijd and the tablet each have something concrete to satisfy rather than an interface invented when the page is built. The branch carried only board files and was cherry-picked to main, so this feature is Backlog again with its requirements intact. ADR-260913-c477cd still stands: its motivation shifts from 'the sources do not exist yet' to 'a lapsed credential should cost one section of the page, not the page', which is the stronger argument anyway.

## Links

- Requirements: [[FEAT-260912-0f2744]]
- [[ADR-260913-c477cd]] — a capability may declare a connector optional
- [[ADR-260913-210e08]] — a capability is handed the connectors it declared
- [[ADR-260912-b22e46]] — tools are one verb each, and why the digest is two
- [[ADR-260912-bd36c2]] — Harry never calls a model
- Decision: [[ADR-260913-c477cd]] — A capability may declare a connector optional, and render without it

