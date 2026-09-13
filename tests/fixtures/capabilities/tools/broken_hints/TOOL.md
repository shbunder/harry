---
name: broken_hints
namespace: broken
description: Its annotations are not annotations
always_load: true
annotations:
  readOnlyHint: [1, 2]
enabled: true
---

Loads perfectly well and then cannot be published, because `readOnlyHint` has to be true or
false and this is a list. `make lint` would catch it in `.harry/`; a capability arriving
through `$HARRY_CAPABILITIES_DIR` never passed anybody's gate.
