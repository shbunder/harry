---
id: FEAT-260912-74f222
title: Anything Claude makes can land on the tablet
status: Backlog
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

## Links

- Requirements: [[FEAT-260912-74f222]]
