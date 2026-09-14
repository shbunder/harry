---
name: remarkable_push_document
namespace: remarkable
description: Put a document on the reMarkable tablet, from a PDF or from markdown
requires: [remarkable]
always_load: false
annotations:
  readOnlyHint: false
  destructiveHint: false
  idempotentHint: false
  openWorldHint: true
enabled: true
---

Puts one document into the tablet's Harry folder, where it appears after the tablet next
syncs. Give it either a `path` to a PDF that already exists, or `markdown` to be rendered
into one — and a `name`, which is what shows on the tablet.

```
{"where": "Harry", "id": "77abc664-09ad-454f-993d-54b91a9a9683",
 "name": "Notes on the NMBS strike"}
```

Reach for this when somebody wants to read something away from a screen: a long piece you
just wrote, a document they asked you to prepare, a summary to annotate with a pen. Markdown
is rendered at the tablet's exact page size, so headings, lists, quotes, tables and code
blocks all come out readable.

**Exactly one of `path` and `markdown`.** Passing both, or neither, is an error — there is
no sensible guess to make between a file and some text.

`name` is what the person sees in their folder, so write it for them: *"Notes on the NMBS
strike"*, not *"output_2.pdf"*. There is no undo from here, so a name that says what it is
saves a person opening three documents to find the right one.

**This writes to a real device.** It adds; it never deletes, moves or renames — Harry has no
tool that can. A document pushed twice under the same name gives two documents, not one.

Not for reading anything back. The tablet is somewhere things go.
