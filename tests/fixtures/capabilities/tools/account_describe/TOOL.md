---
name: account_describe
namespace: account
description: Who Harry thinks is asking, from a tool that awaits
always_load: true
annotations:
  readOnlyHint: true
enabled: true
---

The same answer as account_whoami, from an async function. Every tool that fetches anything
over the network will be async, so that is the branch production mostly takes and the one
worth proving.
