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
    """The forecast, exactly as the connector shaped it.

    Its `available` is kept rather than stripped: this is the one source that reports its own
    failure instead of raising, and that answer is the truth about the morning.
    """
    return dict(weather.forecast())
