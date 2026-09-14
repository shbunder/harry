# Harry — the documentation

| Page | What it covers |
|---|---|
| [operating.md](operating.md) | Running Harry on the NUC, and renewing the two credentials that expire |
| [mcp.md](mcp.md) | Registering Harry with Claude, what gets published, why most tools are not in the list, and what a caller gets when something fails |
| [sources.md](sources.md) | Where the morning page gets its facts, what every source promises, and what the page loses without each one |
| [jobs.md](jobs.md) | What Harry runs on its own clock, what it only watches somebody else's clock for, and what the watchdog can and cannot notice |
| [alerting.md](alerting.md) | Setting up Slack, what a message looks like, why the same fault does not tell you twice, and the two holes it cannot close |
| [capabilities.md](capabilities.md) | How Harry finds what it can do, what a capability writes, and what `/health` says when one is skipped |

A module gets its own page here when it lands, saying: what it does, what it needs in
`.env`, how to get those values, what it does when its source is unavailable, and what it
puts in Slack when that happens. See `.claude/rules/docs-in-impl.md`.
