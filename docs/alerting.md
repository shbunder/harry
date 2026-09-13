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
4. **Invite it** — in Slack, `/invite @Harry` in the channel you want. **This is the step
   people skip.** A bot with `chat:write` still cannot post to a channel it is not in.
5. **Configure it** — in `.harry/connectors/slack/.env.local`, which is gitignored:

   ```
   BOT_TOKEN=xoxb-your-real-token
   CHANNEL=#harry
   ```

Never in `.env` beside it — that file is committed and generated. `make lint` fails if you
edit it.

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
