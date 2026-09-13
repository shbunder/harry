---
name: news_failing
namespace: news
description: Raises, so the failure a caller sees can be checked
always_load: true
annotations:
  readOnlyHint: true
enabled: true
---

Always raises. It exists so that what a caller gets back when a tool fails is a fact this
repository asserts rather than a hope, and so the steering sentence can be checked.
