"""The sheet itself: how big it is, what colour everything is, and the stylesheet.

Every number here was measured against a real reMarkable Paper Pro rather than chosen. The
page is 509.34 x 679.13 points; at any other size the tablet rescales the PDF and the type
goes soft.
"""

from __future__ import annotations

import re

PAGE = (509.34, 679.13)

# Colour e-ink shows blue, red and green best, and shows them pale. Saturated screen colours
# come out muddy, so these are chosen dark and low-chroma.
INK, MUTED, RULE = '#161512', '#6e6a62', '#ddd8cf'
ALLDAY = '#5f7350'
ACCENT = '#9c3d2e'  # the rule beside Claude's note on an article page

PALETTE = {
    # (edge, wash). The edge is darkened well past the named colour on purpose: colour e-ink
    # renders pale, and a true yellow rule is invisible at arm's length on white. The wash
    # carries the hue, the edge carries the contrast.
    'yellow': ('#9a7b16', '#fbf3dd'),
    'green': ('#3f6b3a', '#e9f1e6'),
    'pink': ('#a8447a', '#fbeaf3'),
    'blue': ('#23496b', '#e8eef5'),
    'red': ('#9c3d2e', '#f8ece9'),
    'purple': ('#5b4a8a', '#eeeaf6'),
    'grey': ('#5a5a5a', '#f0efed'),
}
UNCOLOURED = PALETTE['grey']


def colours(setting: str) -> dict[str, tuple[str, str]]:
    """Which colour each calendar gets.

    `Calendar name=colour`, separated by `|`, the same shape `FEEDS` and `SUBSCRIBED` use —
    `Shaun=yellow|Kids=pink`. A calendar nobody named gets grey rather than a colour somebody
    has to decode, and a colour this palette does not carry is ignored rather than guessed.
    """
    chosen: dict[str, tuple[str, str]] = {}
    for entry in (setting or '').split('|'):
        name, _, colour = entry.strip().partition('=')
        if name.strip() and colour.strip().lower() in PALETTE:
            chosen[name.strip()] = PALETTE[colour.strip().lower()]
    return chosen


FIRST_HOUR, LAST_HOUR = 7, 20
ROW = 21.0  # points per hour in the timetable
# The reMarkable's editing toolbar sits down the left edge of the screen, over the page. On a
# Paper Pro — 1620 x 2160 at 229 dpi, which is the 509.34 x 679.13pt page — it measures about
# 24pt across, so the left margin carries that plus the ordinary 34pt of air.
TOOLBAR = 24.0
MARGIN_LEFT, MARGIN_OTHER = 34.0 + TOOLBAR, 34.0
CONTENT = PAGE[0] - MARGIN_LEFT - MARGIN_OTHER  # 417.3pt
GUTTER = 17.0
LEFT_COLUMN = 186.0
LADDER = ((2, 86.0), (2, 70.0), (3, 80.0), (3, 66.0), (4, 66.0), (4, 54.0), (5, 54.0), (6, 48.0), (8, 44.0))
"""The ways the second sheet can be set, most generous first: a picture on every *k*-th story,
and how tall, in points.

**Harry sets the sheet at every one and keeps the fewest pages, then the fullest last page.**
How much room twenty stories take depends on their headlines, their pictures and their
companions, none of which is known before the morning, so the sheet is measured rather than
guessed. Laid out from one real morning on 2026-09-19, a full day of eighteen and a light day
of ten each filled one page to 97%, at different settings.

It stops at 44pt because below that a crop reads as a coloured stripe, and at eight because a
column with no picture in it reads as a list."""
RIGHT_COLUMN = CONTENT - LEFT_COLUMN - GUTTER  # 214.3pt
STRIP = ('08:00', '12:00', '16:00', '20:00', '23:00')
"""The hours the weather panel shows: four across the day, and 23:00 for whether the late
evening is still warm enough to sit outside."""
HOUR_CELL, HOUR_GAP = 25.0, 6.0
STRIP_W = len(STRIP) * HOUR_CELL + (len(STRIP) - 1) * HOUR_GAP  # 149pt


# ---------------------------------------------------------------------------
# Weather, with a face on it


RAW_STYLE = """
@page {
  size: {{PAGE_W}}pt {{PAGE_H}}pt;
  margin: 34pt {{MARGIN_OTHER}}pt 40pt {{MARGIN_LEFT}}pt;
  @bottom-left  { content: string(kicker); font: 7.5pt 'Avenir Next Condensed'; color: {{MUTED}};
                  letter-spacing: 0.12em; text-transform: uppercase; }
  @bottom-right { content: counter(page); font: 8pt Charter, serif; color: {{MUTED}}; }
}
@page :first { @bottom-left { content: none } @bottom-right { content: none } }

body { font-family: Charter, 'Iowan Old Style', Georgia, serif; font-size: 9.6pt;
       line-height: 1.5; color: {{INK}}; margin: 0; }
h1, h2, .display { font-family: Didot, 'Bodoni 72', Georgia, serif; font-weight: normal; }
.label { font-family: 'Avenir Next Condensed', 'Helvetica Neue', sans-serif; font-size: 7.2pt;
         letter-spacing: 0.16em; text-transform: uppercase; color: {{MUTED}}; }

/* ---- masthead ---- */
.masthead { display: flex; align-items: baseline; justify-content: space-between;
            border-bottom: 1.6pt solid {{INK}}; padding-bottom: 9pt; }
.masthead .name { font-family: Didot, serif; font-size: 20pt; letter-spacing: -0.01em;
                  white-space: nowrap; bookmark-level: 1; bookmark-label: "The day"; }
/* The date first, so *its* baseline is the one `align-items: baseline` puts on the
   masthead's. With the weekday on top the date was pushed down against the rule, reading
   like a caption rather than half of a masthead. */
.masthead .when { text-align: right; }
.masthead .when .display { font-family: Didot, serif; font-size: 13pt; line-height: 1; }
.masthead .when .label { margin-top: 3pt; }

/* ---- weather ---- */
.sky { display: flex; align-items: center; gap: 10pt; padding: 9pt 0 10pt;
       border-bottom: 0.6pt solid {{RULE}}; }
.sky .icon { flex: 0 0 auto; }
.sky .now { flex: 0 0 auto; min-width: 46pt; }
.sky .now .deg { font-family: Didot, serif; font-size: 28pt; line-height: 0.95; }
.sky .now .word { font-size: 8.6pt; color: {{MUTED}}; margin-top: 2pt; }
.sky .range { flex: 1 1 auto; min-width: 0; font-size: 8.6pt; color: {{MUTED}};
              line-height: 1.55; padding-left: 4pt; }
.sky .range b { color: {{INK}}; font-weight: normal; }
/* An explicit width, not `auto`: the strip's children have fixed widths, and flex sized the
   strip from its text instead — so the last hour sat 9.6pt into the right margin. The width
   is worked out from the hours in `STRIP`, so one more hour widens it rather than spilling. */
.strip { flex: 0 0 {{STRIP_W}}pt; display: flex; gap: {{HOUR_GAP}}pt; text-align: center; }
.strip .h { width: {{HOUR_CELL}}pt; }
.strip .h .t { font-size: 7pt; color: {{MUTED}}; letter-spacing: 0.06em; }
.strip .h .d { font-family: Didot, serif; font-size: 10.5pt; line-height: 1.1; }
.strip .h .s { margin-top: 1pt; height: 16pt; }

/* ---- intro ---- */
.intro { font-family: Didot, serif; font-size: 11.5pt; line-height: 1.38; margin: 10pt 0 11pt; }

/* ---- the two columns ---- */
.day { display: flex; gap: {{GUTTER}}pt; }
/* Point widths, not percentages: a percentage width on an absolutely positioned child
   inside a flex item sent WeasyPrint's layout into minutes of work for one page. */
.day .left { flex: 0 0 {{LEFT_COLUMN}}pt; min-width: 0; }
.day .right { flex: 0 0 {{RIGHT_COLUMN}}pt; min-width: 0; }
.colhead { display: flex; justify-content: space-between; align-items: baseline;
           border-bottom: 0.6pt solid {{RULE}}; padding-bottom: 4pt; margin-bottom: 7pt; }
/* The way to the second sheet, in the head of the column it follows. It was a button pinned
   under the six stories, and the column it was pinned in was shorter than they were — the
   timetable's hours are absolutely positioned, so the left column has no height of its own —
   so it landed across the fifth. A link in the head is placed by nothing but the head.
   Ink rather than grey, because it is the one thing in the row that goes somewhere. */
.colhead .onward { font-family: 'Avenir Next Condensed', 'Helvetica Neue', sans-serif;
                   font-size: 7.2pt; font-weight: 600; letter-spacing: 0.16em;
                   text-transform: uppercase; color: {{INK}}; white-space: nowrap; }

/* ---- timetable ---- */
.allday { font-size: 8pt; margin-bottom: 2pt; padding-left: 2pt; }
.allday .dot { display: inline-block; width: 5pt; height: 5pt; border-radius: 3pt;
               background: {{ALLDAY}}; margin-right: 5pt; }
.legend { margin: 7pt 0 2pt; }
.legend .key { font-family: 'Avenir Next Condensed', sans-serif; font-size: 6.8pt;
               letter-spacing: 0.08em; text-transform: uppercase; color: {{MUTED}};
               margin-right: 9pt; white-space: nowrap; }
.legend .dot { display: inline-block; width: 5pt; height: 5pt; border-radius: 3pt;
               margin-right: 3pt; }
.grid { position: relative; margin-top: 6pt; }
.hour { position: absolute; left: 0; right: 0; height: {{ROW}}pt; border-top: 0.5pt solid {{RULE}}; }
.hour span { font-family: 'Avenir Next Condensed', sans-serif; font-size: 6.8pt; color: {{MUTED}};
             position: absolute; left: 0; top: 1.5pt; }
.block { position: absolute; border-left: 2.2pt solid; padding: 1.2pt 2pt 0 3.5pt;
         line-height: 1.12; overflow: hidden; }
.block .when { font-family: 'Avenir Next Condensed', sans-serif; font-size: 6.2pt;
               color: {{MUTED}}; letter-spacing: 0.04em; }
.block .what { font-size: 7.4pt; }

/* ---- index ---- */
a { color: inherit; text-decoration: none; }
.item { display: flex; gap: 7pt; padding-bottom: 2pt; margin-bottom: 2pt;
        border-bottom: 0.4pt solid {{RULE}}; }
.item:last-child { border-bottom: none; }
.item .lead { display: block; }
.item .more { display: block; font-size: 6.4pt; color: {{MUTED}}; margin-top: 1pt;
              font-family: 'Avenir Next Condensed', sans-serif; letter-spacing: 0.06em; }
.item .n { font-family: Didot, serif; font-size: 13pt; color: {{MUTED}}; flex: 0 0 14pt;
           line-height: 1; text-align: center; }
.item .n .mark { display: block; margin-top: 2pt; height: 11pt; }
.item .txt { flex: 1; min-width: 0; }
.item .head { font-family: Didot, serif; font-size: 9.6pt; line-height: 1.16; }
.item .src { font-size: 7pt; color: {{MUTED}}; letter-spacing: 0.1em; text-transform: uppercase;
             font-family: 'Avenir Next Condensed', sans-serif; margin-top: 1.5pt; }
.item .thumb { flex: 0 0 40pt; }
.item .thumb img { width: 40pt; height: 30pt; object-fit: cover; }
.item .also { min-width: 0; margin-top: 2pt; padding-left: 5pt; border-left: 0.8pt solid {{RULE}}; }
.item .also .one { display: block; font-size: 6.9pt; line-height: 1.24; color: {{MUTED}};
                   white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.item .also .one b { font-family: 'Avenir Next Condensed', sans-serif; font-weight: normal;
                     letter-spacing: 0.06em; text-transform: uppercase; font-size: 6.2pt; }

/* ---- the second sheet: a broadsheet ---- */
/* Three ruled columns, no section headings: the topic is the mark beside each source, and the
   paper's running order is kept. Headings cost their height whether they head one story or
   four, and a section of two left half a row white — the sheet read as empty. Columns flow, so
   a topic with one story costs one story's height. */
.sheet.two { page-break-before: always; }
.sheet.two .columns { column-count: 3; column-gap: 13pt; column-rule: 0.5pt solid {{RULE}}; }
.story { break-inside: avoid; padding-bottom: 7pt; margin-bottom: 7pt;
         border-bottom: 0.5pt solid {{RULE}}; }
.story .lead { display: block; }
.story .lead img { display: block; width: 100%; object-fit: cover; margin-bottom: 3pt; }
.story .head { display: block; font-family: Didot, serif; font-size: 9pt; line-height: 1.16; }
.story.opens .head { font-size: 11.5pt; }
.story .gist { display: block; font-size: 7.1pt; line-height: 1.3; color: {{MUTED}}; margin-top: 2pt; }
.story .src { display: flex; align-items: center; gap: 3pt; margin-top: 3pt;
              font-family: 'Avenir Next Condensed', sans-serif; font-size: 6.2pt;
              letter-spacing: 0.1em; text-transform: uppercase; color: {{MUTED}}; }
.story .also { min-width: 0; margin-top: 4pt; padding-left: 5pt; border-left: 0.8pt solid {{RULE}}; }
.story .also .one { display: block; font-size: 6.9pt; line-height: 1.24; color: {{MUTED}};
                    white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.story .also .one b { font-family: 'Avenir Next Condensed', sans-serif; font-weight: normal;
                      letter-spacing: 0.08em; text-transform: uppercase; }
.colhead .back { font-family: 'Avenir Next Condensed', sans-serif; font-size: 7.2pt;
                 letter-spacing: 0.12em; text-transform: uppercase; color: {{MUTED}};
                 margin-left: 12pt; white-space: nowrap; }

/* ---- article pages ---- */
article { page-break-before: always; }
/* One row, one baseline: the source on the left and the way home on the right. The rule
   belongs to the row rather than to the kicker, which used to carry it while a floated link
   sat below it looking like an afterthought. */
article .top { display: flex; align-items: baseline; justify-content: space-between; gap: 12pt;
               border-bottom: 0.6pt solid {{RULE}}; padding-bottom: 5pt; margin-bottom: 11pt; }
article .top .back { font-family: 'Avenir Next Condensed', sans-serif; font-size: 7.2pt;
                     letter-spacing: 0.12em; text-transform: uppercase; color: {{MUTED}};
                     white-space: nowrap; }
/* `string-set` takes the whole of this element's text, so the back-link is its sibling and
   never its child — otherwise every running footer reads "VRT NWS ← The front page". */
article .kicker { string-set: kicker content();
                  font-family: 'Avenir Next Condensed', sans-serif; font-size: 7.2pt;
                  letter-spacing: 0.18em; text-transform: uppercase; color: {{MUTED}}; }
article h1 { font-size: 21pt; line-height: 1.1; margin: 0 0 7pt; letter-spacing: -0.005em;
             bookmark-level: 1; bookmark-label: content(); }
article .byline { font-size: 7.6pt; letter-spacing: 0.1em; text-transform: uppercase;
                  font-family: 'Avenir Next Condensed', sans-serif; color: {{MUTED}}; margin-bottom: 11pt; }
article .shot { margin: 0 0 4pt; }
article .shot img { width: 100%; height: 128pt; object-fit: cover; }
article .caption { font-size: 6.8pt; color: {{MUTED}}; margin-bottom: 12pt;
                   font-family: 'Avenir Next Condensed', sans-serif; letter-spacing: 0.06em; }
article .note { font-size: 9.4pt; font-style: italic; border-left: 2.4pt solid {{ACCENT}};
                padding-left: 9pt; margin: 0 0 13pt; color: #2a2620; }
article .body { column-count: 2; column-gap: 15pt; column-rule: 0.4pt solid {{RULE}};
                text-align: justify; hyphens: auto; }
article .body p { margin: 0 0 7pt; }
/* No drop cap: `float` on ::first-letter inside a multi-column box is an AssertionError
   in WeasyPrint 70. A small-caps opener is the newspaper move that survives. */
article .body p:first-of-type:first-line { font-variant: small-caps; letter-spacing: 0.02em; }
article .missing { color: {{MUTED}}; font-style: italic; font-size: 8.4pt; margin-top: 10pt;
                   border-top: 0.4pt solid {{RULE}}; padding-top: 7pt; }
article .lede { font-size: 11pt; line-height: 1.45; text-align: left; }
/* Not `break-inside: avoid` on the whole foot: one companion row was enough to push the
   label, the row and the links onto a page of their own, leaving four fifths of it white.
   Keep the pieces together instead — the label with what it introduces, and each row whole. */
article .alsoread .label { break-after: avoid; }
article .alsoread .item { break-inside: avoid; }
article .ways { break-inside: avoid; }
article .alsoread { clear: both; margin-top: 15pt; padding-top: 9pt;
                   border-top: 0.6pt solid {{RULE}}; }
article .alsoread .label { font-family: 'Avenir Next Condensed', sans-serif; font-size: 7pt;
                           letter-spacing: 0.16em; text-transform: uppercase; color: {{MUTED}};
                           margin-bottom: 6pt; }
article .partof { display: block; font-family: 'Avenir Next Condensed', sans-serif;
                  font-size: 7.4pt; letter-spacing: 0.1em; text-transform: uppercase;
                  color: {{MUTED}}; margin-bottom: 7pt; }
/* The companion rows are the index's own `.item`, so they inherit its type and spacing.
   Only the picture grows: at the foot of a page there is room for one worth looking at. */
article .alsoread .item { padding-bottom: 7pt; margin-bottom: 7pt; }
article .alsoread .item .head { font-size: 10.5pt; line-height: 1.2; }
article .alsoread .item .thumb { flex: 0 0 58pt; }
article .alsoread .item .thumb img { width: 58pt; height: 42pt; }
/* Three cells, and the arrows only ever mean travel. Previous and Next point along the
   paper's order; the front page and the second sheet are jumps, so they carry no arrow —
   "The front page →" read as *forward*, which is the one thing it was not. */
article .ways { display: flex; align-items: flex-start; gap: 10pt;
                margin-top: 13pt; padding-top: 7pt; border-top: 0.5pt solid {{RULE}};
                font-family: 'Avenir Next Condensed', sans-serif; font-size: 7.4pt;
                letter-spacing: 0.1em; text-transform: uppercase; color: {{MUTED}}; }
article .ways .step { flex: 1 1 0; min-width: 0; }
article .ways .step.home { flex: 0 0 auto; text-align: center; }
article .ways .step.on { text-align: right; }
/* `display: block` on each: WeasyPrint writes no link annotation for an `<a>` that is
   itself a flex item, which is how the first back-link ended up untappable. */
article .ways a { display: block; }
article .ways .step.home a + a { margin-top: 2pt; }
article .ways span { display: block; margin-top: 2pt; font-size: 6.6pt; letter-spacing: 0.02em;
                     text-transform: none; color: {{MUTED}}; line-height: 1.2; }
article .kicker .subject { letter-spacing: 0.18em; }
"""


def _filled(css: str) -> str:
    """Named tokens, not positional `%s`.

    The stylesheet carried thirty-two positional placeholders against a tuple kept in the
    same order by hand. Adding one rule in the middle silently shifted every colour after
    it — twice, in one afternoon. `{{NAME}}` rather than `{NAME}` because CSS is full of
    braces, and the assertion at the end is what turns a typo into an error rather than a
    stylesheet with the word None in it.
    """
    for token, value in {
        'PAGE_W': PAGE[0],
        'PAGE_H': PAGE[1],
        'INK': INK,
        'MUTED': MUTED,
        'RULE': RULE,
        'ALLDAY': ALLDAY,
        'ACCENT': ACCENT,
        'ROW': ROW,
        'LEFT_COLUMN': LEFT_COLUMN,
        'RIGHT_COLUMN': RIGHT_COLUMN,
        'MARGIN_LEFT': MARGIN_LEFT,
        'MARGIN_OTHER': MARGIN_OTHER,
        'GUTTER': GUTTER,
        'STRIP_W': STRIP_W,
        'HOUR_CELL': HOUR_CELL,
        'HOUR_GAP': HOUR_GAP,
    }.items():
        css = css.replace('{{' + token + '}}', str(value))
    left = re.findall(r'\{\{[A-Z_]+\}\}', css)
    assert not left, f'unfilled token(s) in the stylesheet: {left}'
    return css


STYLE = _filled(RAW_STYLE)
