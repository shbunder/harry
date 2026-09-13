---
id: FEAT-260913-007e6f
title: Harry can post to any channel it has been invited to, not just one
track: full
created: 2026-09-13
touches: [connectors/slack, tools/slack_post, core/registry, core/loader, docs]
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
- [ ] A connector that registered nothing is absent from the mapping, and the tool that needed it is skipped at start-up with a reason a person can read, not a KeyError
- [ ] slack_post(channel, text) posts one line to that channel and says which channel it went to
- [ ] slack_post with no channel uses CHANNEL, and alerts Harry raises itself still go there unchanged
- [ ] Posting to a channel the bot is not in comes back as an error naming the channel and saying to invite the bot
- [ ] slack_post is deferred and harry_find_tools("slack") finds it, and an all-deferred .harry/tools/ passes the gate now that core always publishes two loaded tools of its own
- [ ] The Slack connector declares `provides: [slack_post]`, which is where the choice to expose it is written down
- [ ] slack_post carries readOnlyHint false, destructiveHint false, idempotentHint false and openWorldHint true
- [ ] With no Slack credential the tool is skipped rather than offered, and Harry starts
- [ ] The tool's module imports harry.sdk and nothing else, and core names neither slack nor slack_post
- [ ] Every page that describes what a capability is handed says nine fields — docs/capabilities.md, .harry/README.md and the three /new-* skills
- [ ] The loader's requirements page points at the ADR that amended it, so a reader who opens the natural page is not told something untrue

## Stories

<!-- Maintained by `board.py new-story`. -->
- [ ] [[STORY-260913-1f89fb]] — A tool can use the connector it declared, without importing it
- [ ] [[STORY-260913-c9ea14]] — Claude picks the channel, and the bot's invitations decide the rest

## Notes

<!-- Appended by `board.py note`. -->

## Links


- Decision: [[ADR-260913-210e08]] — A capability is handed the connectors it declared, and imports none of them

