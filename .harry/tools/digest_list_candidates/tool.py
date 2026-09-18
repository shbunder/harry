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
    nearby_feeds = _split(context.config.get('nearby_feeds'))
    nearby_places = [place.casefold() for place in _split(context.config.get('nearby_places'))]
    nearby_limit = int(context.config.get('nearby_limit') or 0)
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
        elsewhere, nearby = _split_off_the_local_ones(found, nearby_feeds, nearby_places)
        # The local ones go last and are capped, so a paper that files fifty stories a day
        # cannot take the list over. Everything else keeps competing on recency as before.
        close_by = nearby[:nearby_limit]
        kept = (elsewhere[: max(1, wanted - len(close_by))] + close_by)[:wanted]
        headlines = [_only_what_is_chosen_on(one) for one in kept]
        # Named so the brief can say "these are the nearby ones" without Claude re-deriving it
        # from a feed slug that is no longer in the answer.
        here = {one['id'] for one in close_by}
        # The news connector reports its own dead feeds by name; they belong in the same list
        # a caller checks rather than in a second one nobody looks at.
        unavailable += [str(one.get('source', 'a feed')) for one in stories.pop('unavailable', []) or []]

        return {
            'nearby': [one['id'] for one in headlines if one['id'] in here],
            'date': dt.date.today().isoformat(),
            'weather': sky,
            'agenda': day,
            'headlines': headlines,
            'dropped': len(found) - len(headlines),
            'unavailable': sorted(set(unavailable)),
        }


def _split(setting: object) -> list[str]:
    """A `|`-separated setting, as a list. An empty setting is no entries, not one empty one."""
    return [part.strip() for part in str(setting or '').split('|') if part.strip()]


def _split_off_the_local_ones(
    candidates: list[dict], feeds: list[str], places: list[str]
) -> tuple[list[dict], list[dict]]:
    """Everything else, and the local stories that name one of the places.

    A local paper covers a whole province and files all day, so most of what it carries is
    about somewhere else entirely. Naming one of the places is the rule for handing it over —
    a rule a person could apply by hand, which is what keeps it Harry's to apply. **Which
    topic a story belongs to is still Claude's**, decided on the morning from what arrives.

    It is a blunt rule in both directions, on purpose. A story about a village inside one of
    the places, named only by the village, is dropped. A football club carrying a city's name
    matches wherever it is playing. Both were measured on 2026-09-18, and a filter tight
    enough to fix either would be one that reads the story.
    """
    if not feeds or not places:
        return candidates, []
    elsewhere, nearby = [], []
    for one in candidates:
        slug = str(one.get('feed') or str(one.get('id', '')).split('-')[0])
        if slug not in feeds:
            elsewhere.append(one)
            continue
        haystack = f'{one.get("title", "")} {one.get("summary", "")}'.casefold()
        if any(place in haystack for place in places):
            nearby.append(one)
    return elsewhere, nearby


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
