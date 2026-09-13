---
name: listener
description: Writes down every alert it is handed, so a test can read them back
expires: never
enabled: true
---

Somewhere alerts can go that is not Slack. It appends each message to a file beside itself,
because a test that starts the real app cannot see into the module the loader imported —
the file is the only thing both ends share.

It also proves the point the layout rests on: alerting is not Slack. A second somewhere is
another folder, with no core change.
