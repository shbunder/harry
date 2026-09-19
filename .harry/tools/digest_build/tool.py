"""One verb: build the morning page from what Claude chose, and put it on the tablet.

The other half of the pair. `digest_list_candidates` hands over everything today could
contain; this takes back six stories for the front page, ten or so for the second, a line
about each of the six, and an intro — and turns them into a PDF.

**Every judgement on that call is Claude's and none of it is repeated here.** Which stories,
what to say about them, which are the same event, what subject each belongs to. Harry sorts
them into the reader's order, fetches the pictures, lays the sheet out twice so both columns
reach the bottom, and delivers.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from harry.sdk import Context, Registry

from .page import fit, forget, render
from .sheet import STRIP, colours
from .timetable import when

MOST = 12
"""Front-page picks this will accept. The brief asks for six; twelve is headroom, and an
uncapped `picks` is an uncapped PDF at one to two pages each."""

CANDIDATES = 60
"""Candidates asked for when resolving ids. The same ceiling `digest_list_candidates` has, so
an id it offered is an id this can still find."""

MOST_MORE = 20
"""Second-sheet stories. Past about a dozen they do not fit on one sheet and the answer says
so; twenty is the point at which it stops being worth rendering to find out."""


class Unknown(Exception):
    """An id that matches no candidate, or more than one. The caller's mistake, so it raises."""


def resolve(given: str, known: dict[str, dict]) -> str:
    """The candidate this id means.

    One id is a beginning of the other, and exactly one candidate matches. That is arithmetic
    — a string begins another or it does not — which is why Harry may do it at all.

    It is here because a small model gets a sixty-character id wrong in both directions.
    Measured twice on Haiku against a real morning: the first run dropped the last word of two
    ids, and the second, against a brief rewritten to warn about exactly that, rebuilt two
    from the headline and made them longer. Prose did not fix it.
    """
    # An exact match first, and it is load-bearing rather than an optimisation. The news
    # connector disambiguates two same-day stories whose first five title words match by
    # appending `-2`, so `…-de-huur` and `…-de-huur-2` are both real ids and the first is a
    # strict prefix of the second. Without this, asking for the shorter one would be
    # ambiguous — or worse, resolve to the other and print a story nobody chose.
    if given in known:
        return given
    hits = [one for one in known if one.startswith(given) or given.startswith(one)]
    if len(hits) == 1:
        return hits[0]
    if not hits:
        raise Unknown(f'no candidate is {given!r} — run digest_list_candidates again, the feeds move on')
    raise Unknown(f'{given!r} could mean any of {", ".join(sorted(hits))} — send the whole id')


def gather(sources: dict[str, Any], settings: dict[str, Any], picks: list[dict], more: list[dict]) -> dict:
    """Everything the page needs, fetched once.

    Separate from composing because the sheet is laid out twice, and fetching every article
    and every picture twice would double a call that already blocks for minutes.
    """
    news, log = sources['news'], settings['log']
    if news is None:
        raise Unknown('no news connector is configured, so there is nothing to build a page from')

    known = {one['id']: one for one in news.search(limit=CANDIDATES, detail='full')['candidates']}
    mended: list[dict] = []

    def meant(given: str) -> str:
        found = resolve(given, known)
        if found != given:
            mended.append({'asked': given, 'used': found})
            log.info('resolved %r to %r', given, found)
        return found

    def one(story_id: str, note: str, topic: str | None, place: int, front: bool) -> dict:
        got = news.article(story_id)
        return {
            **got,
            'note': note,
            'topic': topic,
            'shot': known[story_id].get('image'),
            'summary': got.get('summary') or known[story_id].get('summary', ''),
            'anchor': f'story{place}',
            'number': place,
            'handed': place,
            'front': front,
        }

    articles: list[dict] = []
    for place, pick in enumerate([*picks, *more], start=1):
        main = one(meant(pick['id']), pick.get('note', ''), pick.get('topic'), place, place <= len(picks))
        # Every related piece gets its own page too. A "see also" you cannot open is a
        # headline, and the tablet has no address bar to type the rest into.
        main['also'] = [
            {
                **one(meant(rid), '', main['topic'], place, False),
                'anchor': f'story{place}-{k}',
                'number': k,
                'lead': main,
            }
            for k, rid in enumerate(pick.get('also') or [], start=1)
        ]
        articles.append(main)

    forecast = _forecast(sources['weather'], log)
    day_events = _events(sources['icloud'], log)
    palette = colours(str(settings['colours']))
    return {
        'today': dt.datetime.now(settings['zone']).date(),
        'name': str(settings['name']),
        'forecast': forecast,
        'strip': _strip(forecast),
        'day_events': day_events,
        'palette': palette,
        'legend': _legend(day_events, palette),
        'articles': articles,
        'mended': mended,
    }


def register(registry: Registry, context: Context) -> None:
    sources = {name: context.connectors.get(name) for name in ('news', 'weather', 'icloud', 'remarkable')}
    config = context.config
    settings = {
        'log': context.log,
        'name': config.get('name') or 'The Morning Page',
        'colours': config.get('colours') or '',
        'zone': ZoneInfo(str(config.get('timezone') or 'Europe/Brussels')),
    }

    @registry.tool
    def digest_build(
        intro: str,
        picks: list[dict],
        more: list[dict] | None = None,
        deliver: bool = True,
    ) -> dict:
        rest = list(more or [])
        if not picks:
            raise Unknown('picks is empty — the front page needs at least one story')
        if len(picks) > MOST:
            raise Unknown(f'{len(picks)} picks is more than the {MOST} this builds')
        if len(rest) > MOST_MORE:
            raise Unknown(f'{len(rest)} second-page stories is more than the {MOST_MORE} this builds')

        forget()
        data = gather(sources, settings, list(picks), rest)
        html, measured = fit(intro, data, settings['log'])
        where = Path(str(config.get('out_dir') or 'out')) / f'{data["today"].isoformat()}.pdf'
        made = render(html, where, settings['log'])

        tablet = sources['remarkable']
        delivered: dict[str, Any] = {'pushed': False, 'why': 'no tablet connector is configured'}
        if not deliver:
            delivered = {'pushed': False, 'why': 'deliver=false — the page is on disk only'}
        elif tablet is not None:
            delivered = _deliver(
                tablet, where, data['today'].isoformat(), str(config.get('folder') or ''), settings['log']
            )

        return {
            'page': made,
            'fits': measured,
            'articles': sum(1 + len(a['also']) for a in data['articles']),
            'front': len(picks),
            'more': len(rest),
            'resolved': data['mended'],
            'delivered': delivered,
        }


def _deliver(tablet: Any, where: Path, name: str, folder: str, log: Any) -> dict:
    """Put the page on the tablet, and say what happened either way.

    **A push that failed must not take the answer down.** The page is rendered and on disk by
    now; raising here loses the path with it, and the brief tells Claude to call `digest_build`
    once more on an error — which would re-fetch every article and re-render the whole PDF at
    06:30 for a tablet that is merely offline.

    The tablet connector has already tried twice and put a line in Slack, so there is nothing
    to add there. What the caller needs is the path and a sentence.
    """
    try:
        return {'pushed': True, **tablet.push(where, name, folder or None)}
    except Exception as error:  # noqa: BLE001 — the page exists; the delivery is the part that failed
        why = f'{type(error).__name__}: {error}'
        log.warning('the page is on disk but not on the tablet: %s', why)
        return {'pushed': False, 'why': why, 'path': str(where)}


def _forecast(weather: Any, log: Any) -> dict:
    """Today's weather, or an empty answer. A dead forecast costs the panel, not the page."""
    if weather is None:
        return {}
    try:
        answer = weather.forecast()
    except Exception as error:  # noqa: BLE001 — one dead source costs one section
        # Logged, like its sibling below. This was the one place a weather failure left no
        # trace anywhere — and it is the place that builds the page.
        log.warning('no weather on the page: %s', error)
        return {}
    if not answer.get('available'):
        log.warning('no weather on the page: %s', answer.get('why'))
        return {}
    return answer


def _strip(forecast: dict) -> str:
    """The hours in `STRIP` that the forecast has, and nothing in place of one it has not."""
    from .marks import face

    return ''.join(
        f'<div class="h"><div class="t">{hour["at"]}</div>'
        f'<div class="d">{hour["temperature"]}°</div>'
        f'<div class="s">{face(hour.get("summary"), size=15)}</div></div>'
        for hour in (forecast.get('hours') or [])
        if hour.get('at') in STRIP
    )


def _events(calendar: Any, log: Any) -> list[dict]:
    """Today's agenda in the shape the timetable draws, or none of it."""
    if calendar is None:
        return []
    try:
        found = calendar.today()
    except Exception as error:  # noqa: BLE001 — a lapsed password costs the column, not the page
        log.warning('no agenda on the page: %s', error)
        return []
    return [
        {
            'all_day': event['at'] == 'all day' or when(event['at']) is None,
            'from': when(event['at']) or 0,
            'to': when(event.get('ends')),
            'title': event.get('title') or '',
            'where': event.get('where') or '',
            'calendar': event.get('calendar') or 'Calendar',
        }
        for event in found
    ]


def _legend(day_events: list[dict], palette: dict[str, tuple[str, str]]) -> str:
    """The calendars with something on today, and their inks.

    Only those: a colour nobody can decode is decoration, and a legend naming four calendars
    when two of them are empty is four things to read instead of two.
    """
    on_today = [name for name in palette if any(e['calendar'] == name for e in day_events)]
    if not on_today:
        return ''
    return (
        '<div class="legend">'
        + ''.join(
            f'<span class="key"><span class="dot" style="background:{palette[name][0]}"></span>{name}</span>'
            for name in on_today
        )
        + '</div>'
    )
