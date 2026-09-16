---
id: STORY-260916-120de6
title: Harry takes the probe's place, and the tunnel survives a reboot
feature: FEAT-260913-fdd33f
status: Backlog
created: 2026-09-16
---

# STORY-260916-120de6 — Harry takes the probe's place, and the tunnel survives a reboot

Part of [[FEAT-260913-fdd33f]].

## Description

Scenarios 5 and 6. Waits on FEAT-260915-2a6ce1 being merged and Harry deployed on the
NUC — both scenarios need the real service running, and nothing is running today.

Harry replaces the probe only after a cloud routine has reached the probe with a token of
its own. The reboot is deliberate and is the one step that restarts marcel's tunnel, so
marcel is checked afterwards the same way it was checked in the first story.

## Acceptance criteria

<!-- These drive the tests. Write checkable statements, not activities.
     Bad:  Wire up the article fetcher
     Good: A De Tijd article whose browser session has expired falls back to its RSS
           summary, and the page still renders -->

- [ ] `HARRY_API_TOKEN` in the NUC's `.env.local` is generated with `openssl rand -hex 32` and is not the throwaway the probe used
- [ ] The `harry` tunnel points at port 7430, `harry-remote` is merged to `main` and the routine set back to it, and a cloud routine calls `digest_list_candidates` through the tunnel and receives the weather, the agenda and the headlines
- [ ] Through the tunnel, a request with no `Authorization` header and one with a wrong token are refused with 401
- [ ] The tunnel runs as `/etc/systemd/system/cloudflared-harry.service` with `User=shbunder` and `--url`, and neither `config.yml` nor `config.yaml` is in any of the five directories `cloudflared` searches, checked immediately before the reboot
- [ ] After a reboot of the NUC, with nobody logging in, the tunnel reconnects and a routine reaches Harry again
- [ ] After the same reboot, marcel's tunnel reconnects and `https://marcel-bot.com/health` answers 200
- [ ] `docs/mcp.md` carries the triage order for a morning with no page — Harry up, tunnel connected, routine's run log, then Harry's logs — and says every one of those reaches Slack as the same sentence

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

