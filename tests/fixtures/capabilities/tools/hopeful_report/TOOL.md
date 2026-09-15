---
name: hopeful_report
namespace: hopeful
description: Reports whichever of its optional connectors turned up
optional: [weather, broken, quiet]
always_load: true
annotations:
  readOnlyHint: true
enabled: true
---

Says which of its optional connectors were there when it loaded. It exists so a test can ask
the question `optional:` is for — **if this connector is missing, is there still something
worth doing?** — and so that each of the three ways a connector can fail to arrive has a name
of its own: never configured (`weather` absent), present and raising (`broken`), and loaded
but registering nothing (`quiet`).
