"""One verb: what today could contain.

Three sources, one call. The morning task is a scheduled thing that must work on its first
try, so the alternative — find three tools, call three tools, reconcile three failures —
is three chances to go wrong before anything is chosen.

**Every source is optional.** A lapsed calendar password costs the agenda column, not the
page, and a Harry with nothing configured at all still answers the shape rather than an
error — which is what lets each source arrive on its own and have somewhere to land.
"""

from typing import Any, Literal

from harry.sdk import Context, Registry

MOST = 60
"""Headlines this will return however much is asked for. Forty is the default and what the
brief asks for; sixty is headroom for a caller that wants to filter afterwards."""


def register(registry: Registry, context: Context) -> None:
    weather = context.connectors.get('weather')
    calendar = context.connectors.get('icloud')
    news = context.connectors.get('news')
    log = context.log

    def section(name: str, call: Any, absent: str) -> tuple[dict, str | None]:
        """One source's answer, or why there is none. Never raises.

        A source that is not configured, a source that broke, and a source that reports its
        own failure are three sentences and one outcome: the page renders without it. All
        three are said out loud — silence is the one thing that looks like "nothing happened
        today".

        **The source's own `available` wins.** The weather connector never raises: it catches
        its own HTTP errors and answers `{'available': False, 'why': …}`, because a forecast
        nobody can get is an answer rather than an error. Forcing `True` over that read as a
        working forecast with no numbers in it, and left `unavailable` empty — so Claude was
        told to say nothing was wrong.
        """
        if call is None:
            return {'available': False, 'why': absent}, name
        try:
            answer = call()
        except Exception as error:  # noqa: BLE001 — one dead source costs one section
            why = f'{type(error).__name__}: {error}'
            log.warning('%s could not answer: %s', name, why)
            return {'available': False, 'why': why}, name
        if answer.get('available') is False:
            log.warning('%s says it could not answer: %s', name, answer.get('why'))
            return answer, name
        return {'available': True, **answer}, None

    @registry.tool
    def digest_list_candidates(
        limit: int = 40,
        detail: Literal['concise', 'full'] = 'concise',
    ) -> dict:
        import datetime as dt

        wanted = max(1, min(limit, MOST))
        unavailable: list[str] = []

        def note(name: str | None) -> None:
            if name is not None:
                unavailable.append(name)

        sky, missing = section(
            'weather', (lambda: forecast_of(weather)) if weather else None, 'no weather connector is configured'
        )
        note(missing)
        day, missing = section(
            'calendar',
            (lambda: {'events': calendar.today()}) if calendar else None,
            'no calendar connector is configured',
        )
        note(missing)
        # Asked for the ceiling and capped here, so `dropped` is a number rather than always
        # zero: the connector caps at whatever it is given and does not say what it left out.
        # It costs nothing — one fetch per feed either way.
        stories, missing = section(
            'news',
            (lambda: news.search(limit=MOST, detail=detail)) if news else None,
            'no news connector is configured',
        )
        note(missing)

        found = stories.pop('candidates', []) if stories.get('available') else []
        headlines = [_only_what_is_chosen_on(one) for one in found[:wanted]]
        # The news connector reports its own dead feeds by name; they belong in the same list
        # a caller checks rather than in a second one nobody looks at.
        unavailable += [str(one.get('source', 'a feed')) for one in stories.pop('unavailable', []) or []]

        return {
            'date': dt.date.today().isoformat(),
            'weather': sky,
            'agenda': day,
            'headlines': headlines,
            'dropped': len(found) - len(headlines),
            'unavailable': sorted(set(unavailable)),
        }


SPENT_HERE = ('image', 'feed')
"""Fields the news connector supplies that nothing on this page is chosen by.

Measured on 2026-09-18, on a 40-headline answer of 21,959 characters: `image` was 14.3% of it
and `feed` 2.8%. Neither comes back — a pick is an id, a note and a topic — and `digest_build`
re-reads the feeds itself, so it resolves the picture from its own copy rather than from
anything the caller returns. `feed` says nothing the id does not: every id begins with that
feed's slug, and `source` is the name a person reads.

**`date` is not one of these, and looks like it should be.** Every candidate carried today's
date the day this was measured, which makes it appear to repeat the answer's own `date`. It
does not: `news.search` applies no date filter, so the newest forty can include yesterday's
stories on a quiet morning, and a candidate that lost its date would be put on today's page
as today's news.

Trimmed here rather than in the connector's `CONCISE_FIELDS`, which `news_search` shares —
there the caller is asking across days and across feeds, and both fields are the answer.
"""


def _only_what_is_chosen_on(candidate: dict) -> dict:
    """One headline, with the fields this page is not chosen by removed."""
    return {key: value for key, value in candidate.items() if key not in SPENT_HERE}


def forecast_of(weather: Any) -> dict:
    """The forecast, exactly as the connector shaped it.

    Its `available` is kept rather than stripped: this is the one source that reports its own
    failure instead of raising, and that answer is the truth about the morning.
    """
    return dict(weather.forecast())
