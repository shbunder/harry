---
name: slack_post
namespace: slack
description: Put a line in a Slack channel
requires: [slack]
always_load: false
annotations:
  readOnlyHint: false
  destructiveHint: false
  idempotentHint: false
  openWorldHint: true
enabled: true
---

Posts one line of plain text to a Slack channel and tells you which channel it went to.

Reach for this when you have finished something the people in a channel are waiting for — a
reading list, a summary, a heads-up that a job is done. Pass the channel as a name with the
hash (`#claude`) or as an id; leave it out and the message goes to the channel Harry was
configured with.

**The bot can only post where it has been invited.** If a channel comes back as
`not_in_channel`, somebody needs to run `/invite @Harry` there — you cannot fix it from
here, and no other channel is affected.

Not for reporting that something broke. Harry sends its own failures to its configured
channel without being asked, and deciding where a failure belongs is a judgement it does not
make. One line only: no formatting, no threads, no mentions.
