# Operating Harry

Harry runs on the NUC in Docker on port 7430. Marcel owns 7420 and 7421.

```bash
make image        # build the image, tagged with this commit
make deploy       # build, tag, and put the real stack on it
make up           # start, and wait until Harry is actually answering
make health       # what loaded, what did not, and why — asked from the host
make logs         # follow
make down         # stop
```

`make up` waits for the healthcheck the image declares, up to two minutes, so it returns
when Harry is serving rather than when the container has been created. A start that never
becomes healthy fails the command instead of leaving you to discover it from `make logs`.

`make down` stops Harry and leaves the `harry-data` volume alone — the store, the rendered
pages and the De Tijd session all survive it, and come back on the next `make up`. Only
`docker compose down -v` deletes them, which is why no make target does that.

Harry restarts itself. `restart: unless-stopped` brings the container back when the process
crashes — measured here: killing it inside the container had it healthy again in under half
a minute — but **not** after you stopped it on purpose, which is what "unless stopped"
means. So `make down` keeps Harry down until you run `make up`.

The same policy is what should bring Harry back after a reboot, and **that has not been
observed on this machine yet** — nothing has rebooted it since Harry was containerised. It
also needs the daemon to start at boot, which is worth checking once:

```bash
systemctl is-enabled docker     # want: enabled
```

## What the NUC needs installed

Docker, and — **to run the gate on this machine** — three system libraries that WeasyPrint
renders the page through:

```bash
sudo apt-get install -y libpango-1.0-0 libpangoft2-1.0-0 libcairo2
```

**Without them `make check` fails 31 tests**, all of them on
`OSError: cannot load library 'libpango-1.0-0'`, in `test_digest_build.py` and
`test_remarkable_connector.py`. Nothing is wrong with the code when that happens; the
renderer has no backend. The container is unaffected either way — the `Dockerfile` installs
the same three, which is why Harry can serve a page on a host that cannot run its own tests.

Worth knowing because there is no CI: `make check` before a push is the only thing between
a change and `main`, so a NUC that cannot run it is a NUC you cannot finish work on.

## A first boot with nothing configured

**A bare Harry is not an empty Harry**, and this is the state every credential arrives into
one at a time. Start it on a machine with no `.env.local` anywhere and `make health`
answers **8 loaded, 7 skipped**:

| | |
|---|---|
| **loaded** | `weather`, `news`, and the tools over them — `weather_forecast`, `news_search`, `news_article`, plus `digest_list_candidates` and `digest_build` |
| | `morning-page` — the job, and with it the watchdog. **It loads on a bare machine**, so a missed 07:00 is noticed from the first boot, before any source is configured |
| **skipped** | `icloud` — *required settings app_password and username are not set* |
| | `remarkable` — *required setting device_token is not set* |
| | `slack` — *required settings bot_token and channel are not set* |
| | `icloud_list_events`, `remarkable_push_document`, `remarkable_list_documents`, `slack_post` — each *needs <connector>, which did not load* |

Weather and news declare no required setting, so both work with nothing configured at all.
The first page you build on a fresh machine therefore has a weather panel and headlines and
no agenda. Nothing crashes: a capability whose configuration is absent disables itself and
says which setting is missing, which is the sentence that tells you where to go next.

The two digest tools name all four connectors under `optional:` rather than `requires:`, so
they load with none of them — a lapsed calendar password costs the agenda column, not the
page.

## Two stacks on one machine

The real one delivers the morning page. The dev one is where a change is tried, and it is
the same image — code is identical, everything else is configuration.

```bash
make up        make up-dev        # start. `make up` never starts dev; the profile sees to that
make down      make down-dev      # stop, each leaving the other running
make logs      make logs-dev      # follow
make health    make health-dev    # what loaded, and whether the clock is on
```

| | Real | Dev |
|---|---|---|
| Port | 7430 | 7431 |
| Container | `harry` | `harry-dev` |
| Volume | `harry-data` | `harry-dev-data` |
| Credentials | `.env.local` | `.env.dev.local` |
| Clock | **on** | **off** |

**How to tell them apart from outside**, with no access to either one's settings: ask
`/health` and read `jobs.enabled`. The real stack answers `true` and lists what it is
watching; dev answers `false` with empty lists.

`make health` asks over the published port from the host rather than from inside the
container, and that is deliberate: reading `/health` by exec-ing in follows `$HARRY_PORT`,
which is exactly what the image's healthcheck does — and there is a misconfiguration where
both follow it to the same wrong place and report healthy while nothing outside can reach
Harry. A check that shares the broken assumption cannot find it.

**The clock is the one real asymmetry, and it is the reason there are two stacks rather
than two ports.** Both would otherwise watch the morning page's 07:00 deadline, and dev
would report a miss for a page the real stack had delivered. A Slack channel that carries
one wrong "no page today" a day stops being read, and then the real one goes unread with
it. So dev schedules nothing, registers no watchdog, and never starts its scheduler —
`HARRY_SCHEDULER_ENABLED=false`, set on the service in `docker-compose.yml`.

Dev has its own volume, so `docker compose down -v` on dev cannot take the real store with
it, and its own credentials file, so a token pasted in to try something is never the token
the morning page is using.

### Why the port is set on the service and not left to a file

Both services pin `HARRY_PORT` and `HARRY_DATA_DIR` under `environment:`, which outranks
`env_file:`. Without that, a stray `HARRY_PORT` in somebody's `.env.local` moves the port
Harry listens on while compose still publishes the old one — and **that failure reports
itself as healthy**, because the image's healthcheck reads the same variable and follows it
to the right place while the outside world knocks on the wrong one. It was measured before
being fixed: `/data` empty, the store written to a path that dies with the container, and
`Container harry Healthy` on the console.

## Putting a credential on the NUC

Harry's secrets arrive as **environment variables**, one file per stack, and never as a file
inside the image. The names are `HARRY_<CAPABILITY>_<SETTING>` — the prefixed spelling of a
capability's own setting, which exists for exactly this: a container has no folders.

```bash
install -m 600 /dev/null .env.local        # if it does not exist yet. 600, before anything goes in it
$EDITOR .env.local
```

```ini
# .env.local — the real stack. Gitignored, mode 600, never leaves this machine.
HARRY_ICLOUD_USERNAME=you@example.com
HARRY_ICLOUD_APP_PASSWORD=abcd-efgh-ijkl-mnop
HARRY_REMARKABLE_DEVICE_TOKEN=<the long token from pairing>
HARRY_SLACK_BOT_TOKEN=xoxb-…
HARRY_SLACK_CHANNEL=#harry
```

Then `make up`. **No rebuild** — the image carries no configuration, so a credential added
here reaches Harry on the next start. Watch it land:

```bash
make health | grep -A1 icloud     # skipped → loaded
```

**Use an editor, not `echo >>`.** A secret typed on a command line is in `~/.bash_history`
and in the process list while it runs, and neither is somewhere you can take it back from.

**One at a time, weather first.** Weather and news need nothing, so they are already working
— start there, then iCloud, then the tablet, checking `make health` after each. A credential
that does not work is much easier to find when it is the only one that changed.

The dev stack reads `.env.dev.local` instead, with the same names. Give it its own
throwaway values where you can: the reMarkable token especially, because there is no
read-only variant and the dev stack pushing to the real tablet is a thing that happens once.

| Setting | Where to get it | Expires |
|---|---|---|
| `HARRY_ICLOUD_USERNAME` | The Apple ID itself | no |
| `HARRY_ICLOUD_APP_PASSWORD` | account.apple.com → Sign-In and Security → App-Specific Passwords. Shown once | when the Apple ID password changes |
| `HARRY_REMARKABLE_DEVICE_TOKEN` | `make remarkable-pair CODE=…`, code from my.remarkable.com/device/desktop/connect | no — but revoking the device kills it |
| `HARRY_SLACK_BOT_TOKEN` | api.slack.com/apps → OAuth & Permissions. Needs `chat:write`, and the bot invited to the channel | no |
| `HARRY_SLACK_CHANNEL` | A channel id like `C0123456789`, or `#harry` | — |

The De Tijd browser session is the exception: it is a file, not a string, and it lives in
the data volume at mode 600. See the renewal steps further down.

### Building a page by hand, before anything is scheduled

The whole product, minus the clock. **`make` is not in the image** — the `Dockerfile` copies
`scripts/` but no `Makefile` — so this goes through `scripts/call_tool.py`, which is what
the make targets shell out to anyway:

```bash
docker compose exec harry uv run python scripts/call_tool.py digest_list_candidates
# choose from what it returns, write the picks, then:
docker compose exec -T harry sh -c 'cat > /data/picks.json' < picks.json
docker compose exec harry uv run python scripts/call_tool.py digest_build --args @/data/picks.json
```

Put `"deliver": false` in the picks and nothing is pushed — the PDF is written to
`/data/digest/<date>.pdf` and stays there. `OUT_DIR` already defaults to `/data/digest`, so
the page lands on the volume without being told to; `out/` is in `.dockerignore` and would
not have survived the container.

**Measured on this NUC:** forty headlines back in under a second, and a 53-page paper with
twenty articles built in **21 seconds**. Worth knowing because a silent MCP call is aborted
after 300s of no progress, and on a laptop this took about ninety.

## Deploying a version, and going back

```bash
make deploy      # build this commit, tag it, put the real stack on it
make rollback    # put the real stack back on the tag it was running before
make versions    # what has been deployed here, and what images are still around
```

**Neither one touches a volume.** The store, the rendered pages and the De Tijd session
outlive every deploy and every rollback, because the only thing either changes is which
image the container is made from.

A build is named after the short commit — `harry:8d49dc2` — because that is the one name
that cannot mean two different things, and a date can mean two within an afternoon. A tree that is not
clean builds as `harry:8d49dc2-dirty` and **`make deploy` refuses it**, naming what is in
the way — including an untracked file, which the `Dockerfile` would copy into the image: there is no CI here,
so the tag is the only record of what shipped, and a tag that cannot be rebuilt from git
records nothing.

The real stack names a tag; the dev stack tracks `latest` on purpose, because dev is where
the newest build is tried.

A worked example. Something is wrong with the page this morning:

```
$ make versions
deployed on this machine, newest first:
  8d49dc2
  2f05e4e
images still present:
  harry:8d49dc2  10 seconds ago
  harry:latest   10 seconds ago
  harry:2f05e4e  About a minute ago

$ make rollback
✓ harry is back on harry:2f05e4e   (make rollback again returns to the other one)
```

`make rollback` swaps the top two, so running it twice returns you to where you started —
useful when the rollback turns out not to have been the problem. It stops and says so if
only one version has ever been deployed here, or if the previous image has been pruned off
the machine, and in the second case it tells you the commit to rebuild from.

`make up` starts the real stack on whatever tag was last deployed, falling back to `latest`
on a machine that has never deployed — which is what lets a fresh clone start without
setting anything up. The record is `.deployed-tags` in the repository root, gitignored,
because which version this machine runs is machine state rather than code.

## Configuration

Two files, and `.env.local` wins:

| File | Committed? | On the NUC it holds |
|---|---|---|
| `.env` | Yes — it arrives with the checkout | Every key with its working default, secrets empty |
| `.env.local` | No | The three credentials, and anything that differs on this machine |

A capability's own settings live in its own folder, beside a committed `.env` that
`make env-template` generates — `.harry/connectors/slack/.env.local` holds the Slack bot
token. **That is the route on a laptop.** In the container it does not exist:
`.dockerignore` keeps every `.env.local` out of the image and nothing mounts one, so on the
NUC the same setting arrives as `HARRY_SLACK_BOT_TOKEN` in the root `.env.local`, which
compose injects as a real environment variable. Same setting, same precedence order, two
spellings — see [Putting a credential on the NUC](#putting-a-credential-on-the-nuc) above.
See also [alerting.md](alerting.md) and [capabilities.md](capabilities.md).

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
August 2026 and needed a patched client. `remarkapy` is pinned exactly in `pyproject.toml`;
expect to move that pin a few times a year.

If a push fails twice, Harry alerts. That alert is the feature — a fire-and-forget job on a
protocol like this fails silently and you notice in three weeks.

## The 50-day rule

On reMarkable's free tier a document untouched for 50 days stops syncing. Irrelevant for a
daily page, relevant if the tablet becomes an archive. Connect is €3.99/month if it starts
to bite.
