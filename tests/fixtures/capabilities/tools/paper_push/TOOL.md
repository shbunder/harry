---
name: paper_push
namespace: paper
description: Declared, with nothing behind it
always_load: false
annotations:
  readOnlyHint: false
enabled: true
---

A TOOL.md that somebody wrote before writing the tool.py beside it. Claude would pick this
and get nothing, which reads as a broken tool rather than an unfinished folder — so the
loader refuses it instead.
