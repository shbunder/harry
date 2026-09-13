---
name: quiet_report
namespace: quiet
description: Needs a connector that registered nothing
requires: [quiet]
always_load: true
annotations:
  readOnlyHint: true
enabled: true
---

Never loads: the connector it declares has nothing to hand over. Exists so that what a
person is shown in that case is a fact rather than a hope.
