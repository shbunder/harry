---
name: slack
description: One-way messages into Slack, so a failure reaches a person instead of a log file
expires: manual
enabled: true
config:
  bot_token:
    description: "Bot token from api.slack.com/apps → your app → OAuth & Permissions. Starts xoxb-. Needs the chat:write scope, and the bot must be invited to the channel."
    secret: true
    required: true
  channel:
    description: "Where messages go — a channel id like C0123456789, or a name like #harry. No default: any default would be somebody else's workspace."
    required: true
---

Harry's only way of telling you something went wrong. One-way, out. Nothing comes back
through here — buttons and slash commands are a second credential and a second inbound
surface, and none of it is needed to stop a failure being silent.

**What Harry sends:** one line, no formatting, no severity. Read on a phone by somebody who
is not debugging it.

> Harry started without the icloud connector: required setting app_password is not set

**When this stops working**, every alert falls back to a WARNING in Harry's log and nothing
else breaks — the caller that was reporting a problem is not taken down by the reporting.
You find out the way you find out about anything unreported: by looking.

## Setting it up

1. **Create the app.** api.slack.com/apps → Create New App → From scratch. Name it Harry,
   pick your workspace.
2. **Give it one scope.** OAuth & Permissions → Scopes → Bot Token Scopes → add
   `chat:write`. Nothing else. It does not need to read anything.
3. **Install it.** Install to Workspace, approve, copy the Bot User OAuth Token — it starts
   `xoxb-`.
4. **Invite it to the channel.** In Slack: `/invite @Harry` in the channel you want. A bot
   with `chat:write` still cannot post to a channel it is not in; Slack answers
   `not_in_channel` and this is the step people skip.
5. **Write the values into `.env.local` beside this file.** Run this — do not edit any file
   in this folder by hand, and never put a token in a file git tracks:

   ```bash
   cat > .harry/connectors/slack/.env.local <<'EOF'
   BOT_TOKEN=paste-the-xoxb-token-here
   CHANNEL=#the-channel-you-invited-it-to
   EOF
   ```

   `.env.local` is the only file here that is gitignored. **This file and `.env` beside it
   are both committed** — a token typed into either is a token in your repository, and the
   block above is a command rather than a form for exactly that reason.

## When it stops working

| Slack says | What happened | What to do |
|---|---|---|
| `invalid_auth` | The token was revoked or rotated | Reinstall the app, copy the new token into `.env.local`, restart Harry |
| `not_in_channel` | The bot is not in that channel | `/invite @Harry` in the channel |
| `channel_not_found` | The channel name or id is wrong, or the bot cannot see it | Check `CHANNEL`. A private channel needs the bot invited before it exists to the bot |
| nothing — the call times out | Slack or the network is unreachable | Nothing to do. The attempt is abandoned after five seconds and logged |

**`expires: manual`** because a bot token does not expire on a clock but does die whenever
somebody reinstalls or revokes the app. Nothing watches it yet: the failed alert is the
alert you needed, and that is a hole a connector health check has to close, not this
connector.
