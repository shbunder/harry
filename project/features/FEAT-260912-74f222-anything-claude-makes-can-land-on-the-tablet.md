---
id: FEAT-260912-74f222
title: Anything Claude makes can land on the tablet
track: full
created: 2026-09-12
touches: [connectors/remarkable]
stories: [STORY-260914-461f63, STORY-260914-6db95b]
decisions: [ADR-260914-6b0608]
---

# FEAT-260912-74f222 — Anything Claude makes can land on the tablet

## Summary

The output surface, and the one holding the most dangerous credential in the repo — the device token grants complete read and write access to every document on the tablet, with no scopes. The protocol is reverse-engineered and it does break: all writes failed in August 2026 and needed a patched client.

## Acceptance criteria

<!-- One box per scenario. These are what the pre-close-verifier builds its
     traceability matrix from. -->

- [ ] A PDF is uploaded under the name given, inside the configured folder, and the answer says the folder and the id
- [ ] A folder that does not exist is created once; the next push finds it rather than making a second
- [ ] A push that fails once is retried exactly once, and a successful retry puts nothing in Slack
- [ ] Two failed attempts raise, and put one line in Slack naming the tablet and why, once per 24 hours
- [ ] A revoked token says so and says to re-pair, rather than reporting a network problem
- [ ] The device token reaches no log line, no exception message and no Slack message
- [ ] With no DEVICE_TOKEN the connector and both tools are skipped, saying what is missing, and the rest of Harry loads
- [ ] `make remarkable-pair CODE=…` exchanges the code once and writes the token to the gitignored .env.local without printing it
- [ ] `remarkable_push_document` takes either a PDF path or markdown text, and neither-or-both is an error naming which
- [ ] Markdown is rendered at 509.34 by 679.13 points before it is pushed
- [ ] `remarkable_list_documents` says what is in the folder, newest first, and an absent folder is an empty list
- [ ] The push tool is readOnlyHint false and destructiveHint false; the list tool is readOnlyHint true; both defer
- [ ] remarkapy is pinned to exactly 0.3.1 with the reason on the same line, and nothing needs a Go rmapi binary
- [ ] A live test pushes a real page to a real tablet, marked live and never in the gate
- [ ] docs/sources.md and the runbook say how to pair, what a failed push does, and what lands in Slack

## Stories

<!-- Maintained by `board.py new-story`. -->
- [ ] [[STORY-260914-461f63]] — Harry can put a page on the tablet, and says so when it cannot
- [ ] [[STORY-260914-6db95b]] — Claude can push a document to the tablet and see what is there

## Notes

<!-- Appended by `board.py note`. -->
- **2026-09-12** — PASS on the rendering half, ahead of the push. WeasyPrint 70.0 imports and renders on this Mac with no brew install pango needed, producing a 9,778-byte PDF at exactly 509.34 x 679.13 pt. The Paper Pro geometry is expressible in plain CSS @page, and the renderer is not a risk.
- **2026-09-12** — Finding against the plan: remarkapy 0.3.1 exposes register_device(code) and register_device_wizard(), so pairing needs no Go rmapi binary. The plan assumed rmapi for the one-time pairing. rmapi may still be worth having as a fallback pusher, but it is not on the critical path and the Dockerfile may not need it.
- **2026-09-13** — reMarkable spike PASS. Paired and pushed: a 9,778-byte PDF rendered at 509.34 x 679.13 pt reached the cloud as 77abc664-09ad-454f-993d-54b91a9a9683. No Connect subscription was needed for the upload to be accepted - pending confirmation it actually appears on the device. Pairing used remarkapy's own register_device(code); the Go rmapi binary was never installed, so the Dockerfile does not need it. Pin remarkapy 0.3.1 exactly: the protocol is reverse-engineered and a release broke every write in August 2026. Token is in ~/.rmapi, outside the repo.
- **2026-09-13** — CONFIRMED ON THE DEVICE. The pushed PDF appeared on the tablet, so the free tier carries cloud sync for a daily push and no Connect subscription is needed. That settles the question two implementers disagreed about. Caveat to carry forward rather than forget: the 50-day rule still applies to a document nobody touches, which is irrelevant for a page replaced every morning and relevant the moment the tablet becomes an archive.

## Links

- Requirements: [[FEAT-260912-74f222]]
- Decision: [[ADR-260914-6b0608]] — remarkapy is pinned to an exact version, and there is no Go rmapi binary

