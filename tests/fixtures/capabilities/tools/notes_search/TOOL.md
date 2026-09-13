---
name: notes_search
namespace: notes
description: Find a note by a word in its title or its text
always_load: false
annotations:
  readOnlyHint: true
  idempotentHint: true
enabled: true
---

Searches the notebook and returns the notes whose title or text contains the word you
pass, newest first, with their ids and the line that matched. Reach for this when you are
looking for something written down rather than something that happened.
