---
name: weather_nosy
namespace: weather
description: Reaches for a connector it never declared
always_load: true
annotations:
  readOnlyHint: true
enabled: true
---

Declares no `requires:` and then asks for a connector anyway. Exists so that what a person
is shown in that case is a fact rather than a hope.
