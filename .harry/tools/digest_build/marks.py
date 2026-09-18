"""Every mark on the page that is not type: the weather faces and the topic badges.

Drawn rather than set in a font. The container has no emoji font, an icon font is another
dependency to pin, and these are a dozen shapes — which also stay sharp at any size, and the
Paper Pro is 229 dpi.
"""

from __future__ import annotations

from .sheet import INK

SUN = '<circle cx="32" cy="32" r="13" fill="{ink}"/>' + ''.join(
    f'<rect x="31" y="3" width="2.4" height="8" rx="1.2" fill="{{ink}}" transform="rotate({a} 32 32)"/>'
    for a in range(0, 360, 45)
)
CLOUD = (
    '<path d="M18 46a11 11 0 0 1 1.6-21.9A15 15 0 0 1 48 27a9.5 9.5 0 0 1-1 19H18z" '
    'fill="{fill}" stroke="{ink}" stroke-width="2.6" stroke-linejoin="round"/>'
)
DROPS = ''.join(
    f'<path d="M{x} 50c0 0-3 4-3 5.6a3 3 0 0 0 6 0C{x + 3} 54 {x} 50 {x} 50z" fill="{{ink}}"/>' for x in (23, 33, 43)
)
FLAKES = ''.join(
    f'<g stroke="{{ink}}" stroke-width="2" stroke-linecap="round">'
    f'<path d="M{x} 50v9M{x - 4} 52.5l8 4M{x - 4} 56.5l8-4"/></g>'
    for x in (24, 40)
)
BOLT = '<path d="M34 47l-9 12h7l-3 10 12-14h-7l4-8z" fill="{ink}"/>'
FOG = ''.join(
    f'<path d="M14 {y}h36" stroke="{{ink}}" stroke-width="2.6" stroke-linecap="round"/>' for y in (44, 51, 58)
)

FACES = {
    'clear': SUN,
    'mainly clear': f'<g transform="translate(-6,-6) scale(0.8)">{SUN}</g>' + CLOUD,
    'partly cloudy': f'<g transform="translate(-6,-6) scale(0.8)">{SUN}</g>' + CLOUD,
    'overcast': CLOUD,
    'fog': FOG,
    'drizzle': CLOUD + DROPS,
    'freezing drizzle': CLOUD + DROPS,
    'rain': CLOUD + DROPS,
    'freezing rain': CLOUD + DROPS,
    'showers': CLOUD + DROPS,
    'snow': CLOUD + FLAKES,
    'snow showers': CLOUD + FLAKES,
    'snow grains': CLOUD + FLAKES,
    'thunderstorm': CLOUD + BOLT,
    'thunderstorm with hail': CLOUD + BOLT,
}


NEWSPAPER = (
    '<rect x="1.5" y="3" width="13" height="10.5" rx="1" fill="none" stroke="{ink}" stroke-width="1.5"/>'
    '<path d="M4 6h5M4 8.5h5M4 11h7M11 6h1.5M11 8.5h1.5" stroke="{ink}" stroke-width="1.3" '
    'stroke-linecap="round"/>'
)
CHIP = (
    '<rect x="4" y="4" width="8" height="8" rx="1" fill="none" stroke="{ink}" stroke-width="1.5"/>'
    '<rect x="6.8" y="6.8" width="2.4" height="2.4" fill="{ink}"/>'
    '<path d="M6 4V1.8M10 4V1.8M6 12v2.2M10 12v2.2M4 6H1.8M4 10H1.8M12 6h2.2M12 10h2.2" '
    'stroke="{ink}" stroke-width="1.3" stroke-linecap="round"/>'
)
BOOK = (
    '<path d="M8 4.2C6.4 2.9 4.2 2.6 1.8 3v9.4c2.4-.4 4.6-.1 6.2 1.2 1.6-1.3 3.8-1.6 6.2-1.2V3'
    'c-2.4-.4-4.6-.1-6.2 1.2z" fill="none" stroke="{ink}" stroke-width="1.5" stroke-linejoin="round"/>'
    '<path d="M8 4.2v9.4" stroke="{ink}" stroke-width="1.3"/>'
)
BALL = (
    '<circle cx="8" cy="8" r="6.2" fill="none" stroke="{ink}" stroke-width="1.5"/>'
    '<path d="M8 1.8v12.4M1.8 8h12.4" stroke="{ink}" stroke-width="1.2"/>'
    '<path d="M3.6 3.6c2.6 2.6 2.6 6.2 0 8.8M12.4 3.6c-2.6 2.6-2.6 6.2 0 8.8" '
    'fill="none" stroke="{ink}" stroke-width="1.2"/>'
)
SPARK = '<path d="M8 1.4l1.7 4.4 4.4 1.7-4.4 1.7L8 13.6l-1.7-4.4L1.9 7.5l4.4-1.7z" fill="{ink}"/>'

HOUSE = (
    '<path d="M2.2 7.4L8 2.6l5.8 4.8" fill="none" stroke="{ink}" stroke-width="1.5" '
    'stroke-linecap="round" stroke-linejoin="round"/>'
    '<path d="M3.8 8.4v5.2h8.4V8.4" fill="none" stroke="{ink}" stroke-width="1.5" '
    'stroke-linejoin="round"/>'
    '<path d="M6.8 13.6V10h2.4v3.6" fill="none" stroke="{ink}" stroke-width="1.3"/>'
)
GLOBE = (
    '<circle cx="8" cy="8" r="6.2" fill="none" stroke="{ink}" stroke-width="1.5"/>'
    '<path d="M1.8 8h12.4" stroke="{ink}" stroke-width="1.2"/>'
    '<path d="M8 1.8c2.4 2.6 2.4 9.8 0 12.4M8 1.8c-2.4 2.6-2.4 9.8 0 12.4" '
    'fill="none" stroke="{ink}" stroke-width="1.2"/>'
)
PIN = (
    '<path d="M8 14.2s4.6-4.3 4.6-7.6a4.6 4.6 0 1 0-9.2 0c0 3.3 4.6 7.6 4.6 7.6z" '
    'fill="none" stroke="{ink}" stroke-width="1.5" stroke-linejoin="round"/>'
    '<circle cx="8" cy="6.5" r="1.8" fill="none" stroke="{ink}" stroke-width="1.3"/>'
)

TOPICS = {
    'regional': ('Nearby', 'Nearby', '#1f6f6b', PIN),
    'belgium': ('Belgium', 'At home', '#3f6b3a', HOUSE),
    'world': ('Abroad', 'Abroad', '#23496b', GLOBE),
    'tech': ('AI & technology', 'AI and technology', '#5b4a8a', CHIP),
    'culture': ('Culture', 'Culture', '#a8447a', BOOK),
    'sport': ('Basketball', 'Basketball', '#9c3d2e', BALL),
    'oddity': ('Worth knowing', 'And one more thing', '#9a7b16', SPARK),
}
"""The subjects worth a shape of their own — and **the order the paper runs in.**

Nearby first, then home, then abroad, then technology, then culture, then sport, then the one
worth knowing — **the paper runs outward from where the reader is.** That order is the reader's, stated once and applied everywhere: the second page's
sections, and the article pages behind both pages, are all laid out in it. A newspaper you
can predict the shape of is one you can read at arm's length without hunting.

Each entry is `(mark, heading, ink, shape)` — the short label that sits beside a source, the
longer one that heads a section, the colour, and the drawing.

**Which topic a story belongs to is Claude's**, handed over with the pick — the same line the
grouping is on. A keyword rule would file every article mentioning a company under technology
on the day one of them is about a court case.

Seven. Six was the limit until a seventh was drawn and looked at: a page rendered on
2026-09-18 with `regional` in the table kept the pin distinguishable from the house, the
globe, the chip, the book, the ball and the spark at eleven points. **An eighth is an open
question rather than a settled one** — render one and look, the way this one was.

A pick with no topic, or one this table does not carry, sorts last and gets no mark rather
than a wrong one.
"""

ORDER = {name: place for place, name in enumerate(TOPICS)}


def in_reading_order(articles: list[dict]) -> list[dict]:
    """The paper's own order: by topic group, and inside a group as Claude handed them over.

    Sorting here rather than asking Claude to hand them over sorted, because the order is a
    rule that can be written down — which makes it Harry's to apply. What goes in which group
    is the judgement, and that stays on the pick.
    """
    return sorted(articles, key=lambda a: (ORDER.get(a.get('topic') or '', len(ORDER)), a['handed']))


def badge(topic: str | None, size: int = 11) -> str:
    """The topic's mark, in the topic's colour, or nothing at all."""
    found = TOPICS.get(topic or '')
    if found is None:
        return ''
    _, _, colour, shape = found
    return f'<svg class="topic" viewBox="0 0 16 16" width="{size}" height="{size}">{shape.format(ink=colour)}</svg>'


def face(summary: str | None, size: int = 50) -> str:
    """A weather icon as inline SVG.

    Drawn rather than set in a font: the container has no emoji font, an icon font is another
    dependency to pin, and these are eight shapes. They also stay sharp at any size, which
    matters on a 229 dpi panel.
    """
    shape = FACES.get(summary or '', CLOUD)
    body = shape.format(ink=INK, fill='#ffffff')
    return f'<svg viewBox="0 0 64 70" width="{size}" height="{int(size * 70 / 64)}">{body}</svg>'
