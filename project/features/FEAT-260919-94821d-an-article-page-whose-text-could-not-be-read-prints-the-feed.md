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

## Links

