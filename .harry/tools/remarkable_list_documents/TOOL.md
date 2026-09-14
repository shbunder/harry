---
name: remarkable_list_documents
namespace: remarkable
description: What is already in the tablet's Harry folder
requires: [remarkable]
always_load: false
annotations:
  readOnlyHint: true
  idempotentHint: true
  openWorldHint: true
enabled: true
---

Lists what Harry has put on the tablet — names, ids and when each was last changed, newest
first.

```
[{"id": "77abc664-09ad-454f-993d-54b91a9a9683",
  "name": "Morning page — Monday 14 September",
  "modified": "2026-09-14T06:30:12Z"}]
```

Reach for this to check whether something arrived, to see what a morning page was called, or
to answer "what's on my tablet from you". An empty list means the folder is empty or has not
been made yet — the first push makes it — and is not an error.

It sees **one folder**, the one Harry pushes into. It is not a view of the whole tablet, and
it does not show anything put there by hand, by the reMarkable app, or by email.

`modified` is what the cloud last recorded, so a page you annotated this morning may still
show yesterday's time until the tablet syncs.
