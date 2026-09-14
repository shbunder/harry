# When something goes wrong, Harry says so

Harry's design is degradation. A feed dies and the page still renders; a credential lapses
and one source falls back; a capability is half-written and the rest come up. **Every one of
those is invisible when it works, which means every one is invisible when it does not.**

A morning page that lost De Tijd three weeks ago looks exactly like a page that had no De
Tijd article that day. That is why alerting is part of the design rather than a nicety.

## What you need

One Slack app, one scope, five minutes:

1. **Create it** — api.slack.com/apps → Create New App → From scratch. Name it Harry, pick
   your workspace.
2. **One scope** — OAuth & Permissions → Bot Token Scopes → `chat:write`. Nothing else. It
   never reads anything.
3. **Install it** — Install to Workspace, then copy the Bot User OAuth Token. It starts
   `xoxb-`.
4. **Invite it** — in Slack, `/invite @Harry` in every channel you want Harry to be able
   to post in. **This is the step people skip.** A bot with `chat:write` still cannot post
   to a channel it is not in, and **inviting it somewhere is the only thing that widens
   where Claude may post** — there is no list in Harry to edit.
5. **Configure it** — run this, rather than editing anything by hand:

   ```bash
   cat > .harry/connectors/slack/.env.local <<'EOF'
   BOT_TOKEN=paste-the-xoxb-token-here
   CHANNEL=#the-channel-you-invited-it-to
   EOF
   ```

**`.env.local` is the only gitignored file in that folder.** `CONNECTOR.md` and `.env` are
both committed, so a token typed into either is a token in your repository — and `.env` is
generated besides, so `make lint` fails if you edit it. If you have already pasted a token
somewhere it should not be, **rotate it**: reinstall the Slack app, take the new token, and
put that one in `.env.local`.

## Two different things go to Slack

**Alerts Harry raises itself** go to `CHANNEL` and nowhere else. Deciding where a failure
belongs is judgement, and Harry does not do judgement.

**Messages Claude sends** go wherever Claude says, with the `slack_post` tool:

```
slack_post(text="the weekly reading list is ready", channel="#claude")
```

Leave the channel out and it goes to `CHANNEL` as well. Claude picks according to what the
message is — a finished piece of work to the channel the people who asked for it are in, a
failure to the alerting channel.

**The bot's invitations are the only boundary.** Posting somewhere it has not been invited
comes back as `not_in_channel` with the fix in the message, and there is nothing to configure
in Harry either way. That is deliberate: a second list here would be wrong the first time you
invite the bot somewhere new.

The tool is not in Claude's tool list by default — most tools are not, because the list is
sent on every request. Claude finds it by asking for it. See [mcp.md](mcp.md).

## What arrives

One line. No formatting, no severity, no prefix.

```
Harry started without the icloud connector: required setting app_password is not set
```

It is read on a phone by somebody who is not debugging it, so the two things it carries are
which capability and why. Harry never composes, ranks or phrases anything — the caller that
raised the alert already knows what happened.

## The same fault does not tell you twice

An alert may carry a **key**. One with a key is sent at most once in 24 hours; one without a
key is always sent, because a caller that did not name the fault cannot have meant "this is
the same one".

That is what stops a machine restarting every ten minutes from sending the same line every
ten minutes.

**The record is in memory, so a restart clears it.** A fault already reported today reports
again after a deploy. That is the right trade while there is no store: Harry restarts when
somebody deploys it, not once an hour.

**A fault nobody heard is not remembered.** If Slack was down when the alert was raised,
nothing was reported — so the key is not recorded and the next occurrence tries again.
Recording it would suppress the retry for a day and the fault would never be heard at all.

## Not configured is not broken

With no Slack credential, an alert is a `WARNING` in Harry's log and nothing else. Harry
starts, everything else works, and `/health` says the slack connector was skipped and which
setting is missing.

A fresh checkout has no token. Alerting that fell over without one would make the
unconfigured case the broken case.

## When Slack itself is the problem

| Slack says | What happened | What to do |
|---|---|---|
| `invalid_auth` | The token was revoked, or somebody reinstalled the app | Copy the new token into `.env.local`, restart Harry |
| `not_in_channel` | The bot is not in that channel | `/invite @Harry` there |
| `channel_not_found` | Wrong name or id, or a private channel the bot cannot see | Check `CHANNEL`; invite the bot first for a private channel |
| nothing at all | Slack or the network is unreachable | Nothing. The attempt is abandoned after **5 seconds**, logged, and the next alert is still attempted |

One attempt, no retry loop. A retry loop around an alert is machinery that hides the thing
it is reporting. Whatever raised the alert is never broken by the reporting — an alert path
that raises takes down the code that was trying to tell you about a problem, which is the
worst possible direction for it to fail in.

**Two holes this cannot close**, named so nobody rediscovers them:

- **If the Slack connector itself failed to load, nothing can report that.** It is in
  `/health` and in the log on the machine you just restarted, and nowhere else. The thing
  that reports failures cannot report its own absence.
- **Nothing checks the token until an alert needs it.** A revoked token is found when the
  alert you needed fails. The declaration carries `expires: manual` so that whatever watches
  credentials will find it — and nothing watches yet.

## How a capability reports its own failure

A connector that knows its feed died, or its credential lapsed, says so:

```python
def fetch(self):
    try:
        ...
    except httpx.HTTPError as error:
        self._context.alert(f'{self.source} has stopped answering: {error}', key='feed-down')
        return []
```

**`log` is for whoever is reading the log. `alert` is for whoever is not.** A note about an
unrecognised weather code is a log line. A feed that has been dead since March is an alert.

`key` makes a fault the same fault — one message a day, however often it happens. Harry
scopes it to your capability, so two connectors can both use `"down"` without silencing each
other and neither has to think about it.

**Your declared secrets are scrubbed from the message** before any sink sees it. An alert
goes further than a log line: the log stays on the machine, this reaches Slack.

It never raises, and it returns whether anybody was told. Two things to know:

- **An alert raised while your capability is still registering goes to the log.** A sink is
  itself a capability and has to load first, so at that moment there is nowhere to send.
  Rare — nearly every alert happens at call time, hours later.
- **A sink must not alert about itself.** The thing that carries the news cannot carry news
  about itself. Harry refuses the re-entry rather than recursing, but the rule is yours.

## Adding somewhere else for alerts to go

Alerting is not Slack. A capability offers itself, in its own `register`:

```python
def register(registry: Registry, context: Context) -> None:
    client = Somewhere(context.config['token'])
    registry.connector(client)
    registry.alerts(client.send)
```

`registry.alerts()` is a **role**, not a kind — it sits alongside `connector()` rather than
using up the folder's one implementation. Harry sends every alert to every sink that
registered.

**Your function must raise if it could not deliver.** A sink that returns quietly on a
failure makes a fault nobody heard about look exactly like one that was reported.

Core holds a list of functions and knows nothing else about any of them. There is no
`if name == 'slack'` anywhere, and a test proves it.
