---
id: STORY-260913-c9ea14
title: Claude picks the channel, and the bot's invitations decide the rest
feature: FEAT-260913-007e6f
status: Backlog
created: 2026-09-13
---

# STORY-260913-c9ea14 — Claude picks the channel, and the bot's invitations decide the rest

Part of [[FEAT-260913-007e6f]].

## Description

The first real tool in `.harry/tools/`, and the first thing that is not a fixture. Slack decides where the bot may post; Harry keeps no second list that would be wrong the first time somebody invites it somewhere.

## Acceptance criteria

<!-- These drive the tests. Write checkable statements, not activities.
     Bad:  Wire up the article fetcher
     Good: A De Tijd article whose browser session has expired falls back to its RSS
           summary, and the page still renders -->

- [ ] slack_post(channel, text) posts one line to that channel and the answer says which channel it went to
- [ ] slack_post with no channel uses CHANNEL from the connector's settings
- [ ] An alert Harry raises itself still goes to CHANNEL, with nothing reconfigured
- [ ] A channel the bot is not in returns not_in_channel, names the channel, and says to invite the bot
- [ ] A channel that does not exist returns channel_not_found the same way
- [ ] slack_post is deferred, and harry_find_tools("slack") finds it and then it can be called
- [ ] With no Slack credential the tool is skipped rather than offered, and Harry starts
- [ ] The tool module imports harry.sdk and nothing else
- [ ] check_capabilities.py and env_template.py --check both pass on the new tool folder

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

