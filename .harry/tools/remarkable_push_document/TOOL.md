---
name: remarkable_push_document
namespace: remarkable
description: Put a document on the reMarkable tablet, from a PDF or from markdown
requires: [remarkable]
always_load: false
annotations:
  readOnlyHint: false
  destructiveHint: true
  idempotentHint: true
  openWorldHint: true
enabled: true
---

Puts one document into Harry's folder on the tablet, where it appears after the tablet next
syncs. Give it either a `path` to a PDF that already exists, or `markdown` to be rendered
into one — and a `name`, which is what shows on the tablet.

```
{"where": "Daily", "id": "77abc664-09ad-454f-993d-54b91a9a9683",
 "name": "Notes on the NMBS strike", "replaced": 0}
```

Reach for this when somebody wants to read something away from a screen: a long piece you
just wrote, a document they asked you to prepare, a summary to annotate with a pen. Markdown
is rendered at the tablet's exact page size, so headings, lists, quotes, tables and code
blocks all come out readable.

**Exactly one of `path` and `markdown`.** Passing both, or neither, is an error — there is
no sensible guess to make between a file and some text.

`name` is what the person sees in their folder, so write it for them: *"Notes on the NMBS
strike"*, not *"output_2.pdf"*. A name that says what it is saves a person opening three
documents to find the right one.

**A name that is already in the folder is replaced, and `replaced` says how many copies went.**
That is what makes a page built twice in one morning one document rather than two identical
ones with no timestamp between them — but it also means **calling this twice with the same
`name` and different content leaves only the second.** Choose a name you mean.

**This writes to a real device.** The new document goes up first and only then is the older
copy of that name moved to the tablet's **trash**, so a push that fails changes nothing and a
mistake is recoverable on the device. Nothing else is ever removed: not another name, not
another folder, not a folder. Harry has no tool that moves or renames anything.

Not for reading anything back. The tablet is somewhere things go.
