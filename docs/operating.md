# Operating Harry

Harry runs on the NUC in Docker on port 7430. Marcel owns 7420 and 7421.

```bash
make image        # build
make up           # start
make logs         # follow
make down         # stop
```

## Configuration

Two files, and `.env.local` wins:

| File | Committed? | On the NUC it holds |
|---|---|---|
| `.env` | Yes — it arrives with the checkout | Every key with its working default, secrets empty |
| `.env.local` | No | The three credentials, and anything that differs on this machine |

A capability's own settings live in its own folder, not here: `.harry/connectors/slack/.env.local`
holds the Slack bot token, beside a committed `.env` that `make env-template` generates.
See [alerting.md](alerting.md) and [capabilities.md](capabilities.md).

You never copy `.env`. You create `.env.local` beside it with only what differs, so a key
added to `.env` later reaches this machine without anyone editing it twice.

Every key is declared once and typed in `harry/config.py`; nothing reads the environment
outside it, and the Makefile reads neither file — that is what keeps the order above
true. `.claude/rules/secrets-and-config.md` has the reasoning.

## Is Harry reachable?

`make probe` is a standing answer to that, and it needs nothing of Harry to be built. It
serves two tools — `ping`, which returns immediately, and `sleep`, which blocks — so
"can this client reach Harry" and "does a long call survive the trip" are separate
questions with separate answers.

```bash
make probe                                   # serve, on the port .env resolves to
make probe ARGS="call --ping"                # reach it
make probe ARGS="call --sleep-reporting 660 --every 30"
make probe ARGS="calls"                      # what has reached it, and when
```

**`calls` is the one worth knowing about.** Every call is logged to
`~/.harry-probe/calls.jsonl`, so a question like *"did the 06:30 task actually reach us"*
has an answer afterwards rather than needing somebody awake at 06:30.

Three exit states, and the third matters: `PASS`, `FAIL`, and `UNKNOWN` for a server that
could not be reached at all. A refused connection is not a finding — reporting it as one
is how "the tunnel was down" becomes "blocking calls do not work".

**Before exposing it anywhere public**, set `HARRY_API_TOKEN` in `.env.local`. Without one
the probe falls back to a token committed in the repo, which guards nothing.

### What it has already settled

A tool call held open for 300s returns; 660s silent is aborted with *"no response or
progress for 300s"*. That ceiling is an **idle** timer, and a progress notification resets
it — 660s reporting every 30s returns fine. So a long-running tool holds open as long as
it reports progress, with nothing configured on the client. The settings that also move it,
if you ever need them: a per-server `timeout` in `.mcp.json`, or
`CLAUDE_CODE_MCP_TOOL_IDLE_TIMEOUT`.

## The credentials that expire quietly

This is the part worth reading before you need it. These degrade Harry without breaking it,
which is exactly why they need an alert rather than a health check.

Three, and they fail in different ways:

| Credential | How it dies | What you see | Can you rotate it? | Where the steps are |
|---|---|---|---|---|
| The De Tijd browser session | On its own, after a few weeks | Articles fall back to their RSS summary | Yes — log in again | Below |
| The iCloud app-specific password | The day you change your Apple ID password, which revokes every one at once | `Agenda unavailable`, and `Calendar: the password was refused` in Slack | Yes — generate a new one | [sources.md § The calendar](sources.md) |
| A published calendar link | When the calendar is republished, or the sharer withdraws it | `Agenda unavailable`, and the link's name in Slack | **Only if the calendar is yours.** Otherwise it is theirs to reissue | [sources.md § A calendar your work publishes](sources.md) |
| The reMarkable device token | Only if you revoke the device at my.remarkable.com | A failed push, and `reMarkable: the tablet refused the token` in Slack | Yes — remove the device and pair again | [sources.md § The tablet](sources.md) |

Two of these are worth knowing before you need them.

Changing your Apple password is a thing you do for unrelated reasons, and it stops Harry's
agenda the same morning.

And **the last row is the only credential here you may not be able to rotate.** A calendar
link published by somebody else — an employer, a shared team calendar — is revoked by
republishing it, which only its owner can do. If such a link leaks, it stays leaked until
they reissue it, and they may never need to. Every other credential in Harry has an
owner-side revocation; this one does not.

### The De Tijd browser session

**Symptom.** De Tijd articles stop arriving with full text and fall back to their RSS
summary. The page still renders. Slack gets *"De Tijd login needs refreshing"*.

**Why.** De Tijd returns 403 to any non-browser client, even for free articles, so Harry
reads it through a real browser using a saved logged-in session. That session expires every
few weeks.

**Fix.** Log in by hand in a headed browser and save the session again:

```bash
make spike S=tijd-login            # headed, logs in, writes the storage state
```

Then copy the file to the NUC's data volume at the path `TIJD_STORAGE_STATE` names.

This is personal use of a subscription you pay for, on your own device. The storage state
is never shared and never committed.

## When no page arrives at all

**Symptom.** Nothing on the tablet, and Harry said nothing.

**Why.** The 06:30 trigger is a Claude scheduled task, outside Harry. Harry cannot report
the absence of something that never asked it for anything.

**Fix.** This is what the watchdog is for. Every five minutes, and once when Harry starts,
it asks of each `trigger: claude` job: has its deadline passed today, in that job's own
timezone, and has nothing finished it since midnight? If so, one message in Slack.

If you got no page *and* no Slack message, **check Harry is up first** (`make logs`) and
only then look at the scheduled task — a watchdog inside Harry cannot report Harry being
switched off. See [jobs.md](jobs.md).

Harry runs no model and holds no provider credential, so there is no token here to renew.
See [ADR-260912-bd36c2](../project/decisions/ADR-260912-bd36c2-harry-never-calls-a-model.md).

## When the tablet stops accepting writes

The reMarkable protocol is reverse-engineered and it does break. All writes failed in
August 2026 and needed a patched client. `rmapi` is pinned exactly in the `Dockerfile`;
expect to move that pin a few times a year.

If a push fails twice, Harry alerts. That alert is the feature — a fire-and-forget job on a
protocol like this fails silently and you notice in three weeks.

## The 50-day rule

On reMarkable's free tier a document untouched for 50 days stops syncing. Irrelevant for a
daily page, relevant if the tablet becomes an archive. Connect is €3.99/month if it starts
to bite.
