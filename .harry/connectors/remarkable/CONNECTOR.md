---
name: remarkable
description: The reMarkable tablet — where a finished page ends up
provides: [remarkable_push_document, remarkable_list_documents]
expires: never
enabled: true
config:
  device_token:
    description: 'The long token from pairing. Get it with: make remarkable-pair CODE=<the 8 characters from my.remarkable.com/device/desktop/connect>. It does not expire, but revoking the device at my.remarkable.com kills it.'
    required: true
    secret: true
  folder:
    description: Which folder on the tablet documents go into. Created at the top level the first time, if it is not already there.
    default: Daily
---

Where Harry's output goes. One write, one folder, and the most dangerous credential in this
repository.

**The device token grants complete read and write access to every document on the tablet,
with no scopes and no expiry.** There is no read-only variant to ask for. That is why this
connector does one thing — add a document — and why deleting, moving and renaming are not
exposed even though the token permits all three.

**What Harry sends:** nothing, in the normal case. A push that fails twice puts one line in
Slack, once per 24 hours.

## Pairing

Once per machine. The code is 8 characters and expires in a few minutes, so fetch it and use
it in the same sitting:

1. Open **my.remarkable.com/device/desktop/connect** and copy the code.
2. Run it:

```bash
make remarkable-pair CODE=abcd1234
```

That exchanges the code for a permanent device token and writes it to
`.harry/connectors/remarkable/.env.local`, which is gitignored. It prints that it worked and
does not print the token.

If the code has already expired you get `the code was refused` — go back and get another.

**The token is not kept in `~/.rmapi`.** A file in a home directory is outside the repository,
which is the good half, and outside the container, which is the bad half: the NUC would have
nowhere to read it from. A container injects `HARRY_REMARKABLE_DEVICE_TOKEN` instead.

To revoke it, go to my.remarkable.com and remove the device. Then pair again.

## What it does

**Whoever is pushing says which folder.** `FOLDER` is the default for a caller that does not
care — an ad-hoc push from Claude, say — and `Daily` is the default for that. A caller that
does care names its own: the morning page has a `folder` setting of its own, and a weekly one
would want a different folder rather than the same.

That is the line this connector draws. It owns the tablet — the credential, the client, the
two attempts, the rule that a push replaces what it supersedes. **Where a given document
belongs is something only the thing producing it knows.**

A folder is created **at the top level** the first time something is pushed to it, and found
rather than re-created after that. Always top level: a caller naming a folder puts documents
beside the others and never inside one of yours.

**Pushing a name that is already in the folder replaces it.** The new document goes up first;
only then is the older copy of that name sent to the tablet's trash. A push that failed
therefore leaves yesterday's page exactly where it was, and the worst this order can do is
leave two copies — which is visible, and what this connector did before.

That removal is the only call Harry makes that takes anything off the tablet, and it is bound
three ways: inside this connector's own folder, matching the name just written exactly, and
never the document just created. reMarkable's delete is a soft delete, so what it takes goes
to the tablet's trash. A removal that fails does not fail the push — the page arrived — but it
does put one line in Slack, because a folder quietly filling with duplicates is not something
anyone notices.

A push that fails is tried **exactly once more**. A retry that works is not a fault and says
nothing. Two failures raise — so whoever asked knows the page did not arrive — and put one
line in Slack.

A failed push costs the delivery and nothing else. Whatever was being pushed is still on
disk where it was, and whoever asked is told it did not arrive.

## When it stops working

| What happened | What you see | What to do |
|---|---|---|
| The cloud is unreachable or slow | Retried once, then `the tablet could not be reached`; one Slack line | Usually transient. The next push is a fresh attempt |
| The token has been revoked | `the tablet refused the token — pair this machine again`; one Slack line | `make remarkable-pair CODE=…` with a fresh code |
| A push succeeds but nothing appears on the device | — | The tablet syncs when it has wifi and the screen is on. Give it a minute, then open the folder |
| A folder appeared that nobody asked for | — | Something pushed with a `folder` of its own. `remarkable_list_documents` shows what is in the configured one; the rest is whatever asked for it |
| Two documents of the same name in the folder | One Slack line saying there is more than one | The removal was refused twice. Delete the older one on the tablet — the newest is the one pushed last, and nothing here will revisit that name because tomorrow's is different |
| Duplicates from before this connector replaced on push | — | A name Harry will push again is cleared by the next push. A name it will not — an older date, a one-off document — has to be deleted on the tablet; nothing here goes looking for them |
| Everything is in a folder called `Harry` and nothing new arrives there | — | The default folder became `Daily` on 15 September 2026. Move them across on the tablet, or put `FOLDER=Harry` in `.env.local` |
| Every write started failing and nothing here changed | Two failures, one Slack line | reMarkable changed the protocol. It happened in August 2026. Bump the exact `remarkapy` pin in `pyproject.toml` and run `make test-live ARGS=tests/test_remarkable_connector.py` |
| A document you never touched disappeared | — | The free tier removes documents nobody opens after 50 days. Irrelevant for a page replaced every morning |
