"""The day drawn as a calendar: blocks as tall as the time they take, in their own colours.

The hard part is overlapping events, and the rule that matters is that **columns are local** —
they belong to the events that actually collide and to nobody else.
"""

from __future__ import annotations

from .sheet import GUTTER, LEFT_COLUMN, UNCOLOURED

FIRST_HOUR, LAST_HOUR = 7, 21

MIN_BLOCK = 13.0  # points: a block shorter than this cannot show even its time
TALLEST, SMALLEST = 34.0, 18.0  # points per hour — see `span`


def when(clock: str | None) -> int | None:
    """`"09:30"` as minutes past midnight, or None.

    The calendar connector answers in `"HH:MM"` because that is what a person reads. A
    timetable needs arithmetic, and minutes are the smallest thing that does it without
    dragging a date and a timezone through every comparison.
    """
    if not clock or len(clock) < 5 or clock[2] != ':':
        return None
    try:
        return int(clock[:2]) * 60 + int(clock[3:5])
    except ValueError:
        return None


def span(day_events: list[dict], room: float) -> tuple[int, int, float]:
    """The first and last hour the timetable shows, and how tall an hour is, in points.

    A fixed scale is wrong in both directions: a day running 07:00 to 21:00 overflows the
    sheet, and a day of three morning meetings leaves two thirds of the column blank. So the
    height comes from the hours shown and the `room` the column was measured to have — never
    below 18pt, where a half-hour meeting cannot show its own name, and never above 34pt, where
    a quiet day looks like a spreadsheet.

    **A quiet day shows more of itself rather than stretching.** Six hours at 34pt came to
    204pt of a 302pt column on 2026-09-19, and the bottom third of the front page was white. So
    while the hours at 34pt would not fill the room, the day runs on an hour later — to 23:00
    at most. The evening is the part of a quiet day still to be planned. That is also what
    keeps an hour to 34pt: the day starts by 08:00, and sixteen hours at 34pt is taller than
    any room a page leaves, so the day always runs on far enough first.

    A day with nothing timed, which is also a calendar that could not be read, shows 07 to 21
    and is sized the same way, so it fits the column like any other day.
    """
    timed = [e for e in day_events if not e['all_day']]
    if timed:
        first = max(min(min(e['from'] // 60 for e in timed), FIRST_HOUR + 1), 5)
        last = min(max(max(((e['to'] or e['from']) // 60) + 1 for e in timed), first + 4), 23)
        while (last - first + 1) * TALLEST < room and last < 23:
            last += 1
    else:
        first, last = FIRST_HOUR, LAST_HOUR
    return first, last, max(room / (last - first + 1), SMALLEST)


def lay_out(events: list[dict]) -> list[tuple[dict, float, float]]:
    """Place overlapping events side by side, the way a calendar application does.

    Returns `(event, left, width)` with both as fractions of the column.

    **The rule that matters is that columns are local.** An earlier version counted the
    largest overlap anywhere in the day and split *every* block by it, so three meetings
    colliding at 09:00 left a lone 20:00 event one third of a column wide. Columns belong to
    the events that actually collide and to nobody else.

    Three steps, which is the standard interval-graph layout — the same one Google Calendar
    and Apple's Calendar use:

    1. **Cluster.** Walk the events in start order and cut a new cluster wherever one starts
       at or after everything before it has finished. A cluster is a run of events that
       transitively overlap; nothing in one cluster can affect the width of another.
    2. **Column.** Inside a cluster, put each event in the first column whose last event has
       finished. That is the smallest number of columns the cluster can be drawn in.
    3. **Expand.** A block then widens rightwards across any column that has nothing
       overlapping it — so the middle of three meetings still fills the space its neighbours
       are not using. This is the step that stops a cluster looking like a grid of slivers.

    Written here rather than taken from a library: it is forty lines, and the layout packages
    that do it carry a rendering engine with them.
    """
    if not events:
        return []

    def finishes(event: dict) -> int:
        # A half hour for an event with no end: long enough to read, short enough that a
        # reminder does not claim an afternoon it never had.
        return event['to'] or event['from'] + 30

    ordered = sorted(events, key=lambda e: (e['from'], finishes(e)))

    placed: list[tuple[dict, float, float]] = []
    cluster: list[list[dict]] = []  # columns, each a list of events
    cluster_ends: int | None = None

    def flush() -> None:
        wide = len(cluster)
        for index, column in enumerate(cluster):
            for event in column:
                # Step 3: how many further columns are free for the whole of this event?
                span = 1
                for other in cluster[index + 1 :]:
                    if any(event['from'] < finishes(o) and o['from'] < finishes(event) for o in other):
                        break
                    span += 1
                placed.append((event, index / wide, span / wide))

    for event in ordered:
        if cluster_ends is not None and event['from'] >= cluster_ends:
            flush()
            cluster, cluster_ends = [], None

        for column in cluster:
            if finishes(column[-1]) <= event['from']:
                column.append(event)
                break
        else:
            cluster.append([event])

        cluster_ends = finishes(event) if cluster_ends is None else max(cluster_ends, finishes(event))

    flush()
    return placed


def timetable(day_events: list[dict], palette: dict[str, tuple[str, str]], room: float) -> str:
    """The day as a proportional timetable, `room` points tall: a block is as tall as the time
    it takes."""
    timed = [e for e in day_events if not e['all_day']]
    first, last, row = span(day_events, room)

    rows = ''.join(
        f'<div class="hour" style="top:{(hour - first) * row:.1f}pt"><span>{hour:02d}</span></div>'
        for hour in range(first, last + 1)
    )

    across = LEFT_COLUMN - GUTTER
    blocks = ''
    for event, left, width in lay_out(timed):
        began = event['from']
        ends = event['to'] or began + 30
        top = (began / 60 - first) * row
        height = max((ends - began) / 60 * row, MIN_BLOCK)
        colour, wash = palette.get(event['calendar'], UNCOLOURED)
        clock = _clock(began) + (f'–{_clock(ends)}' if event['to'] else '')
        blocks += (
            f'<div class="block" style="top:{top:.1f}pt;height:{height:.1f}pt;'
            f'left:{GUTTER + left * across:.1f}pt;width:{width * across - 2:.1f}pt;'
            f'border-left-color:{colour};background:{wash}">'
            f'<span class="when">{clock}</span> '
            f'<span class="what">{escaped(event["title"])}</span></div>'
        )

    all_day = ''.join(
        f'<div class="allday"><span class="dot" style="background:'
        f'{palette.get(e["calendar"], UNCOLOURED)[0]}"></span>{escaped(e["title"])}</div>'
        for e in day_events
        if e['all_day']
    )
    height = (last - first + 1) * row
    return f'{all_day}<div class="grid" style="height:{height:.1f}pt">{rows}{blocks}</div>'


def _clock(minutes: int) -> str:
    """Minutes past midnight, back as `"09:30"` for the block to print."""
    return f'{minutes // 60:02d}:{minutes % 60:02d}'


def escaped(text: str) -> str:
    """Local rather than imported from `page`: `page` imports this module, and two modules
    that import each other are two modules nobody can move."""
    import html

    return html.escape(str(text or ''), quote=True)
