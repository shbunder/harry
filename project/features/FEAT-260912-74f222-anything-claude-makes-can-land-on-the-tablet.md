---
id: FEAT-260912-74f222
title: Anything Claude makes can land on the tablet
track: full
created: 2026-09-12
touches: [connectors/remarkable]
stories: []
decisions: []
---

# FEAT-260912-74f222 — Anything Claude makes can land on the tablet

## Summary

The output surface, and the one holding the most dangerous credential in the repo — the device token grants complete read and write access to every document on the tablet, with no scopes. The protocol is reverse-engineered and it does break: all writes failed in August 2026 and needed a patched client.

## Acceptance criteria

<!-- One box per scenario. These are what the pre-close-verifier builds its
     traceability matrix from. -->

- [ ] A PDF pushed with remarkapy appears in the configured folder on the tablet
- [ ] A remarkable_push_document tool puts markdown or a PDF there from any Claude session
- [ ] A remarkable_list_documents tool says what is already in the folder
- [ ] A push that fails is retried once, and a second failure puts one message in Slack
- [ ] The device token never reaches a log, a span, or an error message
- [ ] rmapi and remarkapy are pinned to exact versions, with the reason recorded beside the pin

## Stories

<!-- Maintained by `board.py new-story`. -->

## Notes

<!-- Appended by `board.py note`. -->
- **2026-09-12** — PASS on the rendering half, ahead of the push. WeasyPrint 70.0 imports and renders on this Mac with no brew install pango needed, producing a 9,778-byte PDF at exactly 509.34 x 679.13 pt. The Paper Pro geometry is expressible in plain CSS @page, and the renderer is not a risk.
- **2026-09-12** — Finding against the plan: remarkapy 0.3.1 exposes register_device(code) and register_device_wizard(), so pairing needs no Go rmapi binary. The plan assumed rmapi for the one-time pairing. rmapi may still be worth having as a fallback pusher, but it is not on the critical path and the Dockerfile may not need it.
- **2026-09-13** — reMarkable spike PASS. Paired and pushed: a 9,778-byte PDF rendered at 509.34 x 679.13 pt reached the cloud as 77abc664-09ad-454f-993d-54b91a9a9683. No Connect subscription was needed for the upload to be accepted - pending confirmation it actually appears on the device. Pairing used remarkapy's own register_device(code); the Go rmapi binary was never installed, so the Dockerfile does not need it. Pin remarkapy 0.3.1 exactly: the protocol is reverse-engineered and a release broke every write in August 2026. Token is in ~/.rmapi, outside the repo.
- **2026-09-13** — CONFIRMED ON THE DEVICE. The pushed PDF appeared on the tablet, so the free tier carries cloud sync for a daily push and no Connect subscription is needed. That settles the question two implementers disagreed about. Caveat to carry forward rather than forget: the 50-day rule still applies to a document nobody touches, which is irrelevant for a page replaced every morning and relevant the moment the tablet becomes an archive.

## Links

- Requirements: [[FEAT-260912-74f222]]
