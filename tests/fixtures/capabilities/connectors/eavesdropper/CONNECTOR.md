---
name: eavesdropper
description: Imports harry.alerts instead of using the context it was handed
expires: never
enabled: true
---

context.alert is the only way in. Reaching for harry.alerts directly would let a capability
see every sink, which is core's business.
