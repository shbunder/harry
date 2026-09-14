---
id: FEAT-260912-0f2744
title: The morning page lands on the tablet before you're up
track: full
created: 2026-09-12
touches: [core/registry, core/loader, jobs/morning-page, tools/digest]
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
- [ ] digest_list_candidates returns today's date, the weather, the agenda and up to 40 headlines with ids, and returns them with no sources loaded at all
- [ ] A source that raises leaves its own section unavailable and the other sections intact
- [ ] digest_build takes an intro and picks of id-and-note, and the front page carries the intro verbatim
- [ ] Each picked article appears with the note Claude wrote above its text, unedited
- [ ] An article whose text could not be fetched still appears with its headline and note, saying the text was unavailable
- [ ] An id that is not among today's candidates is an error naming it
- [ ] The page renders at exactly 509.34 by 679.13 points, with an outline entry per article in the order Claude picked
- [ ] With no tablet connector the page is written under the data volume and the answer says where it went; with one, it is pushed and the answer says that
- [ ] The morning-page job is one markdown file whose brief is served as a prompt and tells Claude the three calls to make
- [ ] `make digest-dry` renders to out/digest.pdf from whatever is configured and says what it could not put on the page

## Stories

<!-- Maintained by `board.py new-story`. -->
- [ ] [[STORY-260914-397bbd]] — A capability can declare a connector optional and still load without it
- [ ] [[STORY-260914-abef7c]] — Claude can see what today could contain, and pick from it
- [ ] [[STORY-260914-46e9e7]] — The page carries what Claude chose and what Claude wrote about it

## Notes

<!-- Appended by `board.py note`. -->

## Links

- Requirements: [[FEAT-260912-0f2744]]
- [[ADR-260913-c477cd]] — a capability may declare a connector optional
- [[ADR-260913-210e08]] — a capability is handed the connectors it declared
- [[ADR-260912-b22e46]] — tools are one verb each, and why the digest is two
- [[ADR-260912-bd36c2]] — Harry never calls a model
- Decision: [[ADR-260913-c477cd]] — A capability may declare a connector optional, and render without it

