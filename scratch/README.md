# Phase 0 spikes

Throwaway scripts that answer one question each, print `PASS` or `FAIL`, and are never
imported by anything. Everything in here except this file is gitignored.

Open one with `/spike <what it proves>`; run one with `make spike S=<name>`.

The six the plan opens with, with one change. The original list had `claude-headless` —
proving `claude -p` could fire from cron inside Harry's container. Harry no longer runs a
model at all (ADR-260912-bd36c2), so that spike is gone and the connector spike took its
place on the critical path.

| Spike | Proves |
|---|---|
| `remarkable-push` | Pairing with `rmapi` and pushing a one-page PDF with `remarkapy` works, and whether the free tier is enough |
| `tijd-login` | A headed Playwright login to De Tijd, saved, then reused headless to pull one full article. **The riskiest one.** |
| `icloud-caldav` | iCloud calendar over CalDAV, and whether Reminders come back as VTODO |
| `blocking-mcp` | An MCP tool call that sleeps five minutes and still returns. **Phase 4 rests on this.** |
| `scheduled-task-reaches-harry` | A Claude scheduled task calling a trivial MCP server over the tunnel. **The digest's trigger, and now on the critical path** — see ADR-260912-bd36c2. |
| `desktop-connector` | Claude Desktop reaching the same server, for the ad-hoc "put this on my tablet" path |

A spike that passes gets its finding written into the feature or ADR that depends on it.
A spike that fails is worth more than one that passes — it changes the plan before the
code exists.
