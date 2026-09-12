---
paths:
  - "**/config.py"
  - "**/.env*"
  - "Dockerfile"
  - "docker-compose.yml"
---

# One typed place for configuration, and three credentials that deserve fear

Every environment variable is declared once, typed, with a comment, in `harry/config.py`.
Nowhere else.

## Two files, and which one wins

| File | Committed? | Holds |
|---|---|---|
| `.env` | **Yes** | Every key Harry has, with its working default. Secrets left empty. |
| `.env.local` | No | The real secrets, plus anything that differs **on this machine** — a port, a data directory, a headed browser. |

Highest precedence first:

1. a real environment variable — `HARRY_PORT=7431 make serve`
2. `.env.local`
3. `.env`

`.env.local` is not a copy of `.env`. It holds only what differs, key by key, and every
other setting still comes from the committed file. That is the whole reason there are
two: a key added to `.env` reaches every machine at once, and no machine has to be
told twice.

### Why there are no `export` prefixes, and why make does not load either file

In the repo this was adapted from, `make` pulled both files in with `-include` and every
key in both had to carry an `export` prefix. `export` in a Makefile puts the value into
the *process environment*, which outranks any dotenv file — so a key exported empty in
the committed file and set without `export` in the machine's file resolved to empty,
silently. The arrangement worked, and it needed a paragraph of documentation to be
survivable.

Harry's Makefile loads neither file. `harry/config.py` is the only reader, so the order
above is simply what it does. Two consequences worth knowing:

- **Nothing in a recipe may read a setting.** A target that needs the port runs
  `python -m harry` and lets the app decide. A make variable holding a port is a second
  owner that will eventually disagree with the first.
- **A `#` in a value is safe.** Make treats `#` as a comment, so
  `SLACK_DEFAULT_CHANNEL=#harry` would have been read as empty.

`tests/test_config.py` makes every line of this fail if it stops being true, including
the worktree case — env files resolve against the working directory, because a worktree
shares the primary checkout's virtual environment and anchoring them to the installed
package would make its `.env.local` read by nothing.

## The three

Named here because they are not ordinary secrets and nothing about them is scoped.

| Credential | What it grants |
|---|---|
| `REMARKABLE_DEVICE_TOKEN` | **Complete read and write access to every document on the tablet.** No scopes, no read-only mode. Anything holding it can do anything. |
| `ICLOUD_APP_PASSWORD` | Full calendar and reminders access on the Apple account |
| `TIJD_STORAGE_STATE` | A live logged-in De Tijd session — a file, not a string, and a valid login for anyone who has it |

All three live only in the NUC's `.env` and its data volume. Never the repo, never a log,
never a span, never an error response, never a Slack message.

This is personal use of a subscription you pay for, on your own device. No redistribution,
no sharing the storage state.

## Never

- `os.environ.get(...)` or `os.getenv(...)` outside `config.py`
- A default that is a real credential, endpoint, account or token
- Put a real secret in `.env`. It is committed. Secrets go in `.env.local`
- Copy `.env` to `.env.local`. A full copy means the next key added to `.env` is shadowed
  by a stale value on every machine that copied it
- `export`-prefix a key in either file, or load either file from the Makefile
- Log, trace, or return a value read from a secret field
- Put a storage-state file anywhere but the data volume

## Always

- Add the field to `Settings` with a comment saying what it is for and, where relevant,
  **how to generate it** — the pairing code URL, the app-password page, the login script
- Add the key to `.env` — the committed one — with the same explanation and the working
  default where one exists. A fresh clone should run without anyone inventing
  configuration
- Leave a value empty in `.env` only when it is a secret, when it is account-specific so
  any default would be wrong, or when empty is itself the setting
- Type secrets `SecretStr` and reach them with `.get_secret_value()` at the point of use
- **Alert when a credential lapses.** The De Tijd session and, on subscription billing, the
  Claude Code token on the NUC both expire quietly. Each needs a "this has lapsed" message
  in Slack, or the digest degrades without saying so

## Why

`.env` is the documentation of what Harry can be configured with, and it is only useful
if it is exhaustive — which is exactly why it is the committed one and not a `.example`
beside it. A template that is not the file anyone actually loads drifts within a month,
because nobody edits it when they add a key to the file they are using. A stray `os.environ.get('SOME_FLAG')` is a setting nobody knows
exists, which cannot be reviewed, containerised, or turned off at 06:30 on a Tuesday.

The typed surface also means a missing required value fails loudly at start-up rather than
quietly inside a job. That is **Alerting**.

## Common rationalizations

| Excuse | Reality |
|---|---|
| "It's a temporary flag" | Add it to `Settings` and delete it when it's temporary-over. |
| "It's not a secret, just a URL" | Endpoints are how you tell the NUC from your laptop. |
| "The default is fine for everyone" | Then it is a constant. Put it in the module. |
| "The token is read-only" | The reMarkable token is not. There is no read-only mode. |
| "I'll copy `.env` to `.env.local` and edit it" | Then every key you did not change is frozen at today's value. Put in only what differs. |
| "The Makefile needs the port" | It needs to start Harry. `python -m harry` knows the port. |
| "I'll add the expiry alert later" | Later is three weeks of a silently worse page. |

## Enforcement

`tests/test_config.py` asserts the precedence by producing it, not by describing it. A
`PreToolUse` hook blocks casual edits to `config.py`, `.env*` and any storage-state file.
`.claude/agents/code-reviewer.md` checks for scattered environment reads and for a secret
reaching a log. Severity: **Critical** — cite **Bounded**.
