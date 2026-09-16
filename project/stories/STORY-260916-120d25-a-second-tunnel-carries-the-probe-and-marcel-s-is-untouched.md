---
id: STORY-260916-120d25
title: A second tunnel carries the probe, and marcel's is untouched
feature: FEAT-260913-fdd33f
status: Backlog
created: 2026-09-16
---

# STORY-260916-120d25 — A second tunnel carries the probe, and marcel's is untouched

Part of [[FEAT-260913-fdd33f]].

## Description

Scenarios 1 and 2. One unit because the tunnel is only proven by something answering
through it, and the probe is the thing that answers without holding a credential.

**Marcel is the neighbour this touches.** Its tunnel runs `cloudflared tunnel run --url
http://localhost:7420 marcel` with no config file, and that is what makes a second tunnel
safe — so Harry's runs the same way and writes nothing into `~/.cloudflared/` except the
credentials file `tunnel create` makes.

**The probe must not carry the real token.** It reads `HARRY_API_TOKEN` through Harry's
settings, and this checkout's `.env.local` holds a real one. Pass a throwaway in the
environment, which outranks `.env.local`, and serve it on a port nothing else owns.

## Acceptance criteria

<!-- These drive the tests. Write checkable statements, not activities.
     Bad:  Wire up the article fetcher
     Good: A De Tijd article whose browser session has expired falls back to its RSS
           summary, and the page still renders -->

- [ ] A tunnel named `harry` exists, and `harry.marcel-bot.com` resolves to it
- [ ] Neither `config.yml` nor `config.yaml` exists in `~/.cloudflared/`, `~/.cloudflare-warp/`, `~/cloudflare-warp/`, `/etc/cloudflared/` or `/usr/local/etc/cloudflared/` after the tunnel is created
- [ ] `cloudflared-marcel.service` has the same `ActiveEnterTimestamp` before and after, `cloudflared tunnel info marcel` still shows connections, and `https://marcel-bot.com/health` answers 200 before and after
- [ ] The probe serves on port 7440 with a throwaway exported as `HARRY_API_TOKEN`, and the fingerprint in its banner matches `printf %s "$HARRY_API_TOKEN" | sha256sum | cut -c1-12` before `cloudflared tunnel run` is started
- [ ] `ping` returns through `https://harry.marcel-bot.com/mcp` with the throwaway token
- [ ] A request with no `Authorization` header at all, and one with a wrong token, are both refused with 401 through the tunnel, and both appear in the probe's server output with their status
- [ ] `docs/mcp.md` says how the tunnel is created and run, how it is deleted — stop the run, `tunnel delete`, then the CNAME in the dashboard — and no longer says `HARRY_PUBLIC_URL` is how Harry is reached off the machine

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

