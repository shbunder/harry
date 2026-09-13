---
name: introspect
description: Hands its own Context back, so what the loader built can be looked at
expires: never
enabled: true
config:
  place:
    description: A setting with a default, to check resolution and the per-person layer
    default: Leuven
---

The eight fields on Context are the contract every capability is written against. This one
exists so a test can check the loader fills them, rather than checking a Context the test
built itself.
