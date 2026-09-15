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

        A source that is not configured and a source that broke are different sentences and
        the same outcome: the page renders without it. Both are said out loud — silence is
        the one thing that looks like "nothing happened today".
        """
        if call is None:
            return {'available': False, 'why': absent}, name
        try:
            return {'available': True, **call()}, None
        except Exception as error:  # noqa: BLE001 — one dead source costs one section
            why = f'{type(error).__name__}: {error}'
            log.warning('%s could not answer: %s', name, why)
            return {'available': False, 'why': why}, name

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
        headlines = found[:wanted]
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


def forecast_of(weather: Any) -> dict:
    """The forecast without the `available` the connector already puts on it.

    `section` adds that key itself, so two sources that shape their answers differently — one
    with `available`, one a bare list — still come back looking the same.
    """
    answer = dict(weather.forecast())
    answer.pop('available', None)
    return answer
