---
name: account_whoami
namespace: account
description: Who Harry thinks is asking
always_load: true
annotations:
  readOnlyHint: true
  idempotentHint: true
enabled: true
---

Returns the name Harry has for whoever is making this call, resolved from the token the
request carried. Useful for checking that a second person's credentials are reaching the
right connector, and for nothing else.
