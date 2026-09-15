---
name: both_lists_report
namespace: both
description: Declares one connector required and another optional
requires: [weather]
optional: [icloud]
always_load: true
annotations:
  readOnlyHint: true
enabled: true
---

Declares one connector each way, so a test can prove the two lists do not interfere: the
required one is guaranteed or the tool is skipped, and the optional one is there only if it
loaded.
