"""The morning page, composed.

One front sheet — masthead, weather, Claude's intro, the day's timetable beside six stories —
then a second sheet of everything else in three columns, then a page per article.

**The front sheet is laid out twice.** The intro is Claude's, so nobody knows how deep it runs
until it has been set, and the all-day band is as tall as today happens to be. A guessed
constant was wrong by 40 points in both directions on consecutive days. So: set it once at a
deliberately short scale, read where the timetable actually begins, and give it every point
between there and the bottom margin.

**The second sheet is laid out once per setting on `LADDER`**, and kept at the fewest pages,
then the fullest last page — for the same reason: what twenty stories take is not known until
they have been set.
"""

from __future__ import annotations

import base64
import html
import re
from pathlib import Path
from typing import Any

import httpx

from .marks import TOPICS, badge, face, in_reading_order
from .sheet import LADDER, PAGE, STYLE
from .timetable import timetable

_SHOTS: dict[str, str] = {}
"""Pictures already asked for, by address — and `''` for one that would not come. A build asks
for the same picture many times: in the index, at the foot of an article, and once for every
setting the second sheet is tried at. A failure is remembered too, because each attempt can
wait fifteen seconds and a dead address was once asked for twenty-four times in one build.

**Emptied at the start of every build.** Harry runs for weeks on a NUC, and yesterday's
addresses are never asked for again — so without `forget()` this is twenty base64 images a
day accumulating for the life of the process, none of it reachable."""


def forget() -> None:
    """Drop the pictures from the last build."""
    _SHOTS.clear()


def picture(url: str | None) -> str:
    """One picture, fetched and embedded as a data URI, or '' if it will not come.

    The news connector hands over the **address**; fetching is this page's job, because forty
    candidates carry about thirty pictures and six get printed. Embedding is not optional: a
    PDF cannot reference a remote image, so the bytes have to be in the file.

    Asked for at most once per address per build, and a picture that will not come costs the
    picture. The story, its headline, its note and its text are untouched.
    """
    if not url:
        return ''
    if url in _SHOTS:
        return _SHOTS[url]
    try:
        # A browser User-Agent, because `images.tijd.be` answers 403 to a plain request and
        # 200 to a browser. Measured — the picture was silently missing from every De Tijd
        # story until this line, and the page simply looked emptier than it should have.
        got = httpx.get(
            url,
            timeout=15,
            follow_redirects=True,
            headers={
                'User-Agent': (
                    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
                    '(KHTML, like Gecko) Chrome/128.0 Safari/537.36'
                )
            },
        )
        got.raise_for_status()
    except httpx.HTTPError:
        _SHOTS[url] = ''
        return ''
    _SHOTS[url] = 'data:image/jpeg;base64,' + base64.b64encode(got.content).decode()
    return _SHOTS[url]


def escaped(text: str) -> str:
    """Anything a feed wrote, made safe to put in the page.

    `html.escape` rather than three replacements by hand: it also takes quotes, and a headline
    with a quote in it is not rare — "Geen gevaar voor andere soorten" was on the front page
    the day this was written.
    """
    return html.escape(str(text or ''), quote=True)


def paragraphs(text: str) -> str:
    out = []
    for chunk in text.split('\n'):
        chunk = chunk.strip()
        if not chunk:
            continue
        # A short line with no full stop is a subheading in every article body seen so far.
        if len(chunk) < 60 and not re.search(r'[.!?:]$', chunk):
            out.append(f'<p class="sub"><b>{escaped(chunk)}</b></p>')
        else:
            out.append(f'<p>{escaped(chunk)}</p>')
    return '\n'.join(out)


def index_entry(a: dict, *, also: bool = True) -> str:
    """One line of the index: number, topic mark, headline, source, picture.

    The headline, the thumbnail and each companion are separate links: nested `<a>` is not
    HTML, and WeasyPrint writes no link annotation for one anyway.

    `also=False` is the same row used at the foot of an article, where the companion list is
    the thing being drawn and would otherwise nest inside itself.
    """
    shot = picture(a['shot'])
    companions = a.get('also') or []
    return (
        f'<div class="item"><div class="n">{a["number"]}'
        f'<span class="mark">{badge(a.get("topic"))}</span></div>'
        f'<div class="txt">'
        f'<a class="lead" href="#{a["anchor"]}">'
        f'<div class="head">{escaped(a["title"])}</div>'
        f'<div class="src">{escaped(a["source"])} · {a["published"][11:16]}</div></a>'
        + (
            '<div class="also">'
            + ''.join(
                f'<a class="one" href="#{r["anchor"]}"><b>{escaped(r["source"])}</b> {escaped(r["title"])}</a>'
                for r in companions[:2]
            )
            + (
                f'<span class="more">+{len(companions) - 2} more at the end of the story</span>'
                if len(companions) > 2
                else ''
            )
            + '</div>'
            if also and companions
            else ''
        )
        + '</div>'
        + (f'<div class="thumb"><a href="#{a["anchor"]}"><img src="{shot}"></a></div>' if shot else '')
        + '</div>'
    )


def to_a_glance(line: str, most: int) -> str:
    """A line cut at a word, with an ellipsis, or left alone if it already fits — so the reader
    sees a phrase that ends, rather than one that stops in the middle of "afbraakwerken".

    Counting characters, not measuring type: it is a rule that can be written down, which is
    the only kind of work Harry does.
    """
    if len(line) <= most:
        return line
    kept = line[:most].rsplit(' ', 1)[0].rstrip(' ,;:–-')
    return f'{kept}…'


def short(headline: str, most: int = 38) -> str:
    """A headline small enough to sit under a Previous or Next label."""
    return to_a_glance(headline, most)


def gist(summary: str | None, most: int = 120) -> str:
    """The first sentence of a feed's summary, as plain text, cut at a word within `most`.

    120 characters is about four lines of the sheet's small type under a headline: enough for
    a sentence that says what happened, short enough that the opener stays a headline.

    Plain because a summary is not always text. KW sends a paragraph, a link and character
    codes such as `&#8230;`, and escaping that as it came printed the angle brackets on the
    page. So the tags are dropped and the codes read — a rule, not a rewording: every word
    printed is the feed's own.

    **Until nothing changes, three times at most**, because ROB tv encodes twice: its summary
    arrives as `&amp;nbsp;`, which reads once as `&nbsp;` and only the second time as a space.
    """
    text = summary or ''
    for _ in range(3):
        plain = html.unescape(re.sub(r'<[^>]+>', ' ', text))
        if plain == text:
            break
        text = plain
    text = ' '.join(text.split())
    ends = text.find('. ')
    return text[: ends + 1] if 0 < ends < most else to_a_glance(text, most)


def article_page(a: dict, family: list[dict], before: dict | None, after: dict | None, more: bool) -> str:
    """One story's page.

    `family` is the other pieces on the same story; `before` and `after` are its neighbours in
    the paper's order. `more` says whether there is a second sheet to go back to — on a day
    with none, a link to it would lead nowhere.

    **The arrows only ever mean travel.** `←` is the story before this one and `→` is the one
    after, in the order the paper is read. Jumping home is not a direction, so the front page
    and the second sheet sit between them with no arrow at all — an earlier version put
    "The front page →" at the foot and the arrow read as *forward*, which is the one thing it
    was not.
    """
    # A story whose text could not be read still earns its page. Claude chose it, and the
    # feed's own summary is real reporting — a blank page would throw away both.
    body = paragraphs(a.get('text') or '')
    if not body:
        why = escaped(a.get('why') or 'the text could not be read')
        body = (
            f'<p class="lede">{escaped(a["summary"])}</p>' if a.get('summary') else ''
        ) + f'<p class="missing">Full text unavailable — {why}. This is the summary the feed carried.</p>'
    lead = a.get('lead')
    shot = picture(a['shot'])
    topic = TOPICS.get(a.get('topic') or '')
    return (
        f'<article id="{a["anchor"]}">'
        # The kicker carries `string-set`, so it holds the source and nothing else — a link
        # inside it would print the whole of "← The front page" in the running footer.
        f'<div class="top"><div class="kicker">{escaped(a["source"])}'
        + (f'<span class="subject" style="color:{topic[1]}"> · {escaped(topic[0])}</span>' if topic else '')
        + '</div><div class="back"><a href="#top">← The front page</a></div></div>'
        + (f'<a class="partof" href="#{lead["anchor"]}">← Part of: {escaped(lead["title"])}</a>' if lead else '')
        + f'<h1>{escaped(a["title"])}</h1>'
        + f'<div class="byline">{escaped(a["source"])} · {a["published"][11:16]}</div>'
        + (
            f'<div class="shot"><img src="{shot}"></div><div class="caption">{escaped(a["source"])}</div>'
            if shot
            else ''
        )
        + (f'<div class="note">{escaped(a["note"])}</div>' if a.get('note') else '')
        + f'<div class="body">{body}</div>'
        + '<div class="foot">'
        + (
            # The same row the front page uses — number, topic, headline, picture — because
            # a companion piece is chosen the same way the lead was, and a line of grey text
            # does not read like something worth opening.
            '<div class="alsoread"><div class="label">The same story elsewhere</div>'
            + ''.join(index_entry(r, also=False) for r in family)
            + '</div>'
            if family
            else ''
        )
        + '<div class="ways">'
        + (
            f'<div class="step back"><a href="#{before["anchor"]}">← Previous'
            f'<span>{escaped(short(before["title"]))}</span></a></div>'
            if before
            else '<div class="step back"></div>'
        )
        + '<div class="step home"><a href="#top">The front page</a>'
        + ('<a href="#more">Other news</a>' if more else '')
        + '</div>'
        + (
            f'<div class="step on"><a href="#{after["anchor"]}">Next →'
            f'<span>{escaped(short(after["title"]))}</span></a></div>'
            if after
            else '<div class="step on"></div>'
        )
        + '</div></div></article>'
    )


def story(a: dict, *, opens: bool, tall: float) -> str:
    """One story on the second sheet.

    **The story opening a run leads it**: its picture, `tall` points high, a larger headline,
    and the first sentence of its summary. The others are headline and source — a column of
    pictures is a catalogue, and the white between a few of them is what lets a headline be
    read. A story with no picture or no summary leads with what it has.

    Every headline is printed whole: a narrow column wraps it rather than clipping it. No note,
    even when Claude wrote one — the front page argues for six stories and this is a glance
    across the rest; the note is on the story's own page. Its companions each get a line.
    """
    shot = picture(a['shot']) if opens else ''
    said = gist(a.get('summary')) if opens else ''
    companions = a.get('also') or []
    return (
        f'<div class="story{" opens" if opens else ""}"><a class="lead" href="#{a["anchor"]}">'
        + (f'<img src="{shot}" style="height:{tall:.0f}pt">' if shot else '')
        + f'<span class="head">{escaped(a["title"])}</span>'
        + (f'<span class="gist">{escaped(said)}</span>' if said else '')
        + f'<span class="src">{badge(a.get("topic"), size=9)}'
        f'<span>{escaped(a["source"])} · {a["published"][11:16]}</span></span></a>'
        + (
            '<div class="also">'
            + ''.join(
                f'<a class="one" href="#{r["anchor"]}"><b>{escaped(r["source"])}</b> {escaped(r["title"])}</a>'
                for r in companions
            )
            + '</div>'
            if companions
            else ''
        )
        + '</div>'
    )


def second_page(articles: list[dict], every: int, tall: float) -> str:
    """Everything worth knowing that is not on the front, in three columns and in the paper's
    own order: home, abroad, technology, culture, sport, nearby, and the one worth knowing.

    **No section headings.** Each story carries its topic's mark instead. A heading costs its
    height whether it heads one story or four, and a section of two left half a row white — so
    the sheet read as empty, and the brief asked for four a category to hide it.

    Every `every`-th story opens a run, with a picture `tall` points high. Which setting a day
    gets is `fit`'s to decide.
    """
    if not articles:
        return ''
    stories = ''.join(story(a, opens=place % every == 0, tall=tall) for place, a in enumerate(articles))
    return (
        '<div class="sheet two" id="more"><div class="colhead">'
        '<span class="label">Also today</span>'
        f'<span class="label">{len(articles)} more</span>'
        '<span class="back"><a href="#top">← The front page</a></span></div>'
        f'<div class="columns">{stories}</div></div>'
    )


def compose(intro: str, data: dict, room: float, sheet: tuple[int, float] = LADDER[0]) -> str:
    """The whole document, with `room` points of column for the timetable and the second sheet
    set at `sheet` — a picture every so many stories, and how tall."""
    today, forecast = data['today'], data['forecast']
    day_events, articles = data['day_events'], data['articles']

    front = in_reading_order([a for a in articles if a['front']])
    # Numbered in the order they are read, not the order they were handed over: the paper
    # sorts itself by topic, so 1 is the first Belgian story whatever position it arrived in.
    for place, a in enumerate(front, start=1):
        a['number'] = place
    rest = in_reading_order([a for a in articles if not a['front']])
    index = ''.join(index_entry(a) for a in front)
    inside = second_page(rest, *sheet)
    # The way to the rest, in the head of the column. Without it the second sheet is reachable
    # only by swiping, and a reader who reads the front page and stops never learns there was
    # more. A `span` around the link because WeasyPrint writes no link for an `<a>` that is
    # itself a flex item, and the head is a flex row.
    onward = '<span class="onward"><a href="#more">Other news →</a></span>' if rest else ''

    # The article pages run in the paper's order too, front-page stories and second-page ones
    # together: the reader who taps a story on page two lands in the same sequence they would
    # have reached by turning pages.
    # One flat sequence: every story and every companion, in the order the paper is read.
    # Previous and Next walk this list, so they never point at a page that is not there.
    sequence: list[tuple[dict, list[dict]]] = []
    for a in in_reading_order([*front, *rest]):
        sequence.append((a, a['also']))
        for r in a['also']:
            # A companion's own family is the lead piece first, then its siblings.
            sequence.append((r, [a] + [s for s in a['also'] if s is not r]))

    pages = ''
    for place, (a, family) in enumerate(sequence):
        before = sequence[place - 1][0] if place else None
        after = sequence[place + 1][0] if place + 1 < len(sequence) else None
        pages += article_page(a, family, before, after, more=bool(rest))

    word = forecast.get('summary') or ''
    place = escaped(forecast.get('place') or '')
    # Each time prints on its own, so a forecast that carried one of the two still says it.
    sun = ' · '.join(
        f'{name} {escaped(at)}'
        for name, at in (('Sunrise', forecast.get('sunrise')), ('Sunset', forecast.get('sunset')))
        if at
    )
    week = today.isocalendar().week
    return f"""<title>Morning page</title><style>{STYLE}</style>
<div class="masthead" id="top">
  <div class="name">{escaped(data['name'])}</div>
  <div class="when"><div class="display">{today:%-d %B %Y}</div>
    <div class="label">{today:%A} · Week {week}</div></div>
</div>

<div class="sky">
  <div class="icon">{face(forecast.get('summary'))}</div>
  <div class="now"><div class="deg">{forecast.get('high', '–')}°</div>
    <div class="word">{escaped(word)}</div></div>
  <div class="range"><b>High {forecast.get('high', '–')}°</b> · Low {forecast.get('low', '–')}°<br>
    Rain {forecast.get('rain_chance', '–')}%{f' · {place}' if place else ''}{f'<br>{sun}' if sun else ''}</div>
  <div class="strip">{data['strip']}</div>
</div>

<div class="intro">{escaped(intro)}</div>

<div class="day">
  <div class="left">
    <div class="colhead"><span class="label">The day</span>
      <span class="label">{len(day_events)} entries</span></div>
    {data['legend']}
    {timetable(day_events, data['palette'], room)}
  </div>
  <div class="right">
    <div class="colhead"><span class="label">In this page</span>{onward}</div>
    <div class="list">{index}</div>
  </div>
</div>
{inside}
{pages}
"""


BOTTOM = PAGE[1] - 40.0  # the page's content stops here: 40pt of bottom margin
INTRO_GAP = 11.0  # `.intro`'s margin-bottom, which is what pushes `.day` down
SLACK = 7.0  # points the box model adds under the timetable, measured once


def _boxes(page) -> list[tuple[str, float, float]]:
    """Every classed box on one rendered page, as `(class, top, bottom)` in points.

    WeasyPrint reports positions in CSS pixels. Everything else here is points, and comparing
    the two silently cost an afternoon once already.
    """
    found: list[tuple[str, float, float]] = []

    def walk(box):
        element = getattr(box, 'element', None)
        classes = element.get('class', '').split() if element is not None else []
        if classes:
            found.append((classes[0], box.position_y * 72 / 96, (box.position_y + box.height) * 72 / 96))
        for child in getattr(box, 'children', ()):
            walk(child)

    walk(page._page_box)
    return found


def fit(intro: str, data: dict, log: Any) -> tuple[str, dict]:
    """Lay the front sheet out twice, so the timetable reaches the bottom of the page, and the
    second sheet once per setting, so it fills the pages it takes.

    The intro is Claude's, so nobody knows how deep it runs until it has been set, and the
    all-day band is as tall as today happens to be. A guessed constant was wrong by 40pt in
    both directions on consecutive days. So: set it once at a deliberately short scale, read
    where the timetable actually begins, and give it every point between there and the
    bottom margin.
    """
    from weasyprint import HTML

    probe = HTML(string=compose(intro, data, room=120.0)).render()
    first = _boxes(probe.pages[0])
    intro_ends = max((low for name, _, low in first if name == 'intro'), default=210.0)
    day_top = intro_ends + INTRO_GAP

    everywhere = [box for page in probe.pages for box in _boxes(page)]
    left_top = next(top for name, top, _ in everywhere if name == 'left')
    grid_top = next(top for name, top, _ in everywhere if name == 'grid')
    # Above the timetable: the column head, the legend and the all-day band, all of which
    # change with the day, so all of which are measured rather than assumed. The column's own
    # bottom cannot be measured the same way — flex stretches it to whichever column is
    # taller, so it reports the *other* column's height. Hence a small constant below.
    above = grid_top - left_top
    room = BOTTOM - day_top - above - SLACK

    news_ends = max((low for name, _, low in everywhere if name == 'item'), default=0.0)
    news_top = next(top for name, top, _ in everywhere if name == 'right')
    have, fills = BOTTOM - day_top, news_ends - news_top
    log.info(
        'the day column starts at %.0fpt and has %.0fpt; the timetable gets %.0fpt, '
        'and the news fills %.0fpt (%+.0fpt against the page)',
        day_top,
        have,
        room,
        fills,
        fills - have,
    )
    sheet = settle(in_reading_order([a for a in data['articles'] if not a['front']]), log)
    return compose(intro, data, room=room, sheet=(sheet['every'], sheet['picture'])), {
        'timetable': round(room, 1),
        'column': round(have, 1),
        'news': round(fills, 1),
        'sheet': sheet,
    }


TOP = 34.0  # the page's content starts here: 34pt of top margin


def settle(articles: list[dict], log: Any) -> dict:
    """The setting the second sheet is set at: the fewest pages, then the fullest last page.

    Every setting on `LADDER` is tried by rendering the sheet on its own — the stylesheet and
    the sheet, nothing else — which costs about a second each once the pictures are fetched.
    **Fewest pages first**, because a day that fits one page should get one: a fuller second
    page is not worth turning to. Among those, the one that leaves least white under its
    columns.

    No fill is too low. The page can hold only what the day gave — three stories fill a third
    of a page at any setting — and adding stories is Claude's call, not Harry's.
    """
    from weasyprint import HTML

    if not articles:
        return {'every': LADDER[0][0], 'picture': LADDER[0][1], 'pages': 0, 'filled': 0.0}
    tried = []
    for every, tall in LADDER:
        done = HTML(string=f'<style>{STYLE}</style>{second_page(articles, every, tall)}').render()
        lowest = max((low for _, _, low in _boxes(done.pages[-1])), default=TOP)
        tried.append((len(done.pages), (lowest - TOP) / (BOTTOM - TOP), every, tall))
    pages, filled, every, tall = min(tried, key=lambda one: (one[0], -one[1]))
    log.info(
        'the second sheet: %d stories set with a picture every %d at %.0fpt, %d page(s), the last %.0f%% full',
        len(articles),
        every,
        tall,
        pages,
        filled * 100,
    )
    return {'every': every, 'picture': tall, 'pages': pages, 'filled': round(filled, 2)}


SECOND_SHEET_PAGES = 2
"""How many pages "also today" may run to before it counts as crowded: the front page, at most
two pages of index, then the articles — the owner's rule.

`settle` keeps the sheet to the fewest pages the ladder can reach, and eighteen real stories
fit one page at 96%. **Three pages is still reachable**: companions add a line each under their
story and nothing caps them, so twenty stories with nine companions apiece run to three even
at the leanest setting. This said three pages could not be reached once before, on the
strength of test stand-ins, and a real morning reached them the next day. When it fires the
sheet still renders, a page longer, and the answer says so."""


def render(html: str, where: Path, log: Any) -> dict:
    """The PDF on disk, and what is worth knowing about it.

    Two things are checked rather than assumed, because both were wrong at some point and
    neither is visible from the answer: the front sheet is one page, and so is the second.
    A flex box does not split, so the day column lands wholly on page two the moment it is a
    point too tall — and a reader who has turned past the front page wants everything else at
    a glance, not a second and third helping of it.
    """
    from weasyprint import HTML

    where.parent.mkdir(parents=True, exist_ok=True)
    document = HTML(string=html).render()
    document.write_pdf(where)
    first = document.pages[0]

    crowded = []
    if 'day' not in [name for name, _, _ in _boxes(first)]:
        crowded.append('the day column did not fit on the front sheet')
    spread = [n for n, one in enumerate(document.pages, start=1) if 'sheet' in [c for c, _, _ in _boxes(one)]]
    if len(spread) > SECOND_SHEET_PAGES:
        crowded.append(
            f'"also today" runs to {len(spread)} pages, past the {SECOND_SHEET_PAGES} it should — '
            'fewer stories, or fewer companions under them, would bring it back'
        )
    for what in crowded:
        log.warning('%s', what)

    return {
        'path': str(where),
        'pages': len(document.pages),
        'size': [round(first.width * 72 / 96, 2), round(first.height * 72 / 96, 2)],
        'links': sum(len(one.links) for one in document.pages),
        'crowded': crowded,
    }
