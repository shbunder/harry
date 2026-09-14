---
id: STORY-260914-636ac0
title: A dead feed says so in Slack and costs nothing else
feature: FEAT-260912-24d052
status: Backlog
created: 2026-09-14
---

# STORY-260914-636ac0 — A dead feed says so in Slack and costs nothing else

Part of [[FEAT-260912-24d052]].

## Description

Every way a feed can fail, and what a person hears about it.

This is the story the feature exists for. A dead news feed is invisible — the list is
shorter and the page reads like a quiet Tuesday. Weather can afford to stay silent because
the page prints `Weather unavailable` where the forecast should be. News has no such place,
so the only thing that says a source died is Slack.

It is separate from the first story because its tests are the ones that have to be able to
fail: delete the `try` and a test goes red, delete the `context.alert` and a different one
does.

## Acceptance criteria

- [ ] A feed answering 404 leaves the other feeds' candidates intact, and `news_search` lists that source in `unavailable` with why
- [ ] A feed is waited on for 10 seconds and asked once — the timeout is the argument passed, not a resolved default, and nothing retries
- [ ] A feed answering 200 with HTML instead of XML does the same
- [ ] A feed whose document declares `<!DOCTYPE` before its root element is refused without being parsed, and does the same
- [ ] Every feed being down gives an empty candidate list and every feed in `unavailable`
- [ ] `candidates()` stays a plain list and never grows an `unavailable` key — the digest learns about a dead feed from Slack
- [ ] A failing feed puts one line in Slack naming the source and what happened
- [ ] A feed that has already failed within 24 hours puts nothing further in Slack
- [ ] The Slack line for a 404 is exactly `VRT NWS: VRT NWS answered 404` — no URL, nothing from the response body
- [ ] A `FEEDS` entry that is not `slug=Name=url` is skipped with a log line and the other feeds still load; `FEEDS` empty raises at registration, so the connector is skipped rather than loading with nothing to read
- [ ] `news_search` followed by three `news_article` calls within one minute, all through MCP, fetch each feed once; a call after 5 minutes fetches again
- [ ] A feed that failed is not served from the cache on the next call

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

