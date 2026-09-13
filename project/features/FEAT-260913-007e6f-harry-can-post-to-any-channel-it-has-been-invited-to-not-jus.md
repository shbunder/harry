---
id: FEAT-260913-007e6f
title: Harry can post to any channel it has been invited to, not just one
track: full
created: 2026-09-13
touches: [connectors/slack, tools/slack_post, core/registry, core/loader]
stories: [STORY-260913-1f89fb, STORY-260913-c9ea14]
decisions: [ADR-260913-210e08, ADR-260913-18a8ae, ADR-260912-b22e46]
---

# FEAT-260913-007e6f — Harry can post to any channel it has been invited to, not just one

## Summary

Claude chooses where a message goes, according to what the message is: a failure to the alerting channel, a finished piece of work to the channel the people who asked for it are in. That is a tool rather than a setting, and exposing one is an explicit choice.

It also closes a gap nothing had noticed. A tool declares `requires: [slack]`, the loader refuses the tool when the connector is missing — and nothing ever hands the connector over. Every tool so far has been a fixture returning a dictionary. This is the first real one, and it needs the other half of that contract.

## Acceptance criteria

<!-- One box per scenario. These are what the pre-close-verifier builds its
     traceability matrix from. -->

- [ ] A tool declaring `requires: [slack]` is handed what that connector registered, in context.connectors, and nothing it did not declare
- [ ] A connector that registered nothing is absent from the mapping, and the tool that needed it is skipped at start-up with the reason
- [ ] slack_post(channel, text) posts one line to that channel and says which channel it went to
- [ ] slack_post with no channel uses CHANNEL, and alerts Harry raises itself still go there unchanged
- [ ] Posting to a channel the bot is not in returns not_in_channel, names the channel, and says to invite the bot
- [ ] slack_post is deferred, and harry_find_tools("slack") finds it
- [ ] With no Slack credential the tool is skipped rather than offered, and Harry starts
- [ ] The tool's module imports harry.sdk and nothing else, and core names neither slack nor slack_post

## Stories

<!-- Maintained by `board.py new-story`. -->
- [ ] [[STORY-260913-1f89fb]] — A tool can use the connector it declared, without importing it
- [ ] [[STORY-260913-c9ea14]] — Claude picks the channel, and the bot's invitations decide the rest

## Notes

<!-- Appended by `board.py note`. -->

## Links


- Decision: [[ADR-260913-210e08]] — A capability is handed the connectors it declared, and imports none of them

