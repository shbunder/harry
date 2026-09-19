---
id: FEAT-260919-94821d
title: An article page whose text could not be read prints the feed's summary as text
track: story
created: 2026-09-19
touches: [tools/digest_build]
stories: [STORY-260919-07a6c2]
decisions: []
---

# FEAT-260919-94821d — An article page whose text could not be read prints the feed's summary as text

## Summary

When a story's text cannot be read, its page prints the summary the feed carried instead.
KW sends that summary as HTML — a paragraph, character codes such as `&#8230;`, and WordPress's
footer *"The post … appeared first on KW.be."* — and the page printed all of it, tags and
all. ROB tv encodes its codes twice, so the page would print `&nbsp;`. The page now prints
the summary as the text a reader would have seen on the paper's site, and leaves plain
summaries exactly as they were.

The second sheet already reads a summary this way for its first sentence; both now share one
rule.

## Acceptance criteria

- [x] A KW story whose text could not be read prints its summary on its page as text — its sentences, "…" for `&#8230;`, no tag, no character code — and without WordPress's "The post … appeared first on KW.be." footer
- [x] A ROB tv story whose text could not be read prints no `&nbsp;` and no character code on its page
- [x] A De Tijd summary with a real ampersand ("politiek & economie") prints the ampersand as written
- [x] The second sheet's summary line for a KW story is unchanged: its first sentence as text

## Stories

<!-- Maintained by `board.py new-story`. -->
- [x] [[STORY-260919-07a6c2]] — The fallback summary is plain text, without WordPress's footer

## Notes

<!-- Appended by `board.py note`. -->
- **2026-09-19** — Reflection: pre-close verifier APPROVE WITH NOTES; traceability 8/8. Two Important findings acted on before merge in 747dd4b: the footer pattern ran across paragraphs (now the last paragraph only), and an empty summary was announced as present (now 'The feed carried no summary either'); two suggestions taken too (only tag-shaped tokens are stripped; the loop runs until nothing changes). Six mutants, all killed. Degraded path exercised: an unreadable article with KW, ROB tv and De Tijd summaries from recorded fixtures, plus three written edge cases. Scope drift: none. make check green on the merge commit with FEAT-260919-e9cab2 alongside (1023 passed).

## Lessons Learned

**What worked**

- **The recorded fixtures already held every case.** KW's HTML and WordPress footer, ROB tv's
  twice-encoded `&amp;nbsp;`, and De Tijd's real ampersand were all in `tests/fixtures/news/`;
  a ten-line scan over every recorded `description` (markup, codes, footer, per feed) found
  them before any code was written.
- **A plain-text case that must not change.** De Tijd's "politiek & economie" passed before the
  fix and after it, and killed two over-corrections (ampersands dropped, text escaped twice).

**What to do differently**

- **Write a regex's scope into its test, not only its target.** The footer pattern matched the
  footer — and, with `DOTALL`, everything from any earlier paragraph beginning "The post". The
  verifier found it by feeding it a paper's own sentence. Every "drop X" rule needs a case
  where something that looks like X must stay.
- **`$(ls … | sort | tail -1)` is not "the feature I just made".** Ids sort by their hash after
  the date, so it picked the finished `f580cd` and `board.py new-story` wrote into its feature
  file. Pass the id the CLI printed.
- **pypdf reads small caps back as capitals** ("Na eeN welverdieNde"): the first line of an
  article's text is set in small caps. Compare text taken from there with `says()`.

**Patterns to reuse**

- `plain()` and `FOOTER`/`TAG` in `.harry/tools/digest_build/page.py`: a feed summary to text —
  drop the platform's footer (last paragraph only), strip tag-shaped tokens, unescape until
  nothing changes (each changing pass shortens the text, so it ends).
- Parametrizing one `digest_build` test over `(recorded feed, item title)` *and* literal
  edge-case strings in the same list, with `title=None` meaning "the string is the summary".

## Links

