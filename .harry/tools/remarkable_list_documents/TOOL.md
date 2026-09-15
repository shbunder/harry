---
name: remarkable_list_documents
namespace: remarkable
description: What is already in Harry's folder on the tablet
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
  "modified": "2026-09-14T11:17:06.339000Z"}]
```

Reach for this to check whether something arrived, to see what a morning page was called, or
to answer "what's on my tablet from you". An empty list means the folder is empty or has not
been made yet — the first push makes it — and is not an error.

Newest first, 50 at most. The folder holds a page a day and the free tier drops untouched
documents after fifty, so the cap is a ceiling rather than something you will meet — pass a
smaller `limit` when you only want to know what arrived today.

It sees **one folder at a time**, and by default the one Harry pushes ad-hoc documents into.
Pass `folder` to look somewhere else — the morning page has a folder of its own, so
`remarkable_list_documents(folder="🗞️ Daily")` is how you check whether today's paper arrived.
An empty list from the default folder does not mean the page is missing; it means the page is
not there.

It is not a view of the whole tablet, and it does not show anything put there by hand, by the
reMarkable app, or by email.

`modified` is UTC, and it is what the **cloud** last recorded — so a page you annotated this
morning may still show yesterday's time until the tablet syncs.
