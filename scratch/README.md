# Phase 0 spikes

Throwaway scripts that answer one question each and are never imported by anything.
Everything in here except this file is gitignored.

Open one with `/spike <the question>`; run one with `make spike S=<name>`.

## Three exit states, not two

| Prints | Means |
|---|---|
| `PASS` | It works, with the evidence on the same line |
| `FAIL` | It does not work, after **two attempts at least an hour apart** |
| `UNKNOWN` | It could not be reached, or was tried only once. **Not a finding** |

That third state is the point. A spike that failed because the service was down looks
exactly like one that failed because the design is wrong, and only one of those should
change a plan.

## The six, and what each settles

| Spike | Story | Settles |
|---|---|---|
| ~~`test-server`~~ | `835929` | **Promoted out of here** to `scripts/mcp_probe.py` — `make probe`. It answers the same question every time the tunnel, the client or the host changes, so it stopped being throwaway. |
| `scheduled-task` | `76bb6b` | **Whether the morning page has a trigger at all.** Can a Claude scheduled task reach a self-hosted MCP server? On the critical path — nothing in Phase 1 is safe to build until this answers. |
| `blocking-call` | `f7cda6` | Whether a tool call held open for five minutes returns. **The whole Slack loop rests on it**; a failure makes `ask_human` a request id plus a poll. The transport half is settled — `make probe ARGS="call --sleep 300"` — and what remains is whether a Claude Code session holds. |
| `tijd-login` | `8d003e` | Whether a saved browser session pulls a full De Tijd article. **The riskiest.** A failure costs that source its full text, not the page. |
| `remarkable-push` | `8bc2b4` | Whether a PDF reaches the tablet, and whether the free tier carries it — two implementers disagree, and five minutes beats designing around a guess. |
| `icloud-caldav` | `bdf4d2` | Whether iCloud answers, and whether Reminders arrive as VTODO. The flakiest dependency in the plan, and it blocks only one section. |

Two spikes the original plan listed are deliberately gone. `claude-headless` proved
`claude -p` could fire from cron inside Harry's container, and Harry no longer runs a model.
`desktop-connector` is the same question as `scheduled-task` from a different client, so it
waits until there is a reason to ask it twice.

## A spike is not done when it prints

**The finding goes on the board**, as a dated note on the feature that depends on it —
`board.py note FEAT-… "…"`, quoting what was measured. The requirements page for this
feature has the table of which finding goes where.

Not a requirements page: most of those are still templates, and a finding written into a
blank template is a finding nobody reads. Not a terminal scroll either.

A spike that fails is worth more than one that passes. It changes the plan before the code
exists, which is the only time that is cheap.

And a spike that turns out to be worth keeping gets promoted rather than deleted. One
already has.
