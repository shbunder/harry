"""Today's forecast for one place, from Open-Meteo.

One GET, no account, no key. The smallest source Harry has, and the one that proves the
connector shape before anything with a credential depends on it.

Two callers want two different shapes of the same failure, so there are two methods over one
request. `today()` is what the morning page calls and returns `None` when it has nothing —
the page prints "Weather unavailable" and the rest renders. `forecast()` is what the tool
calls and says *why*, because a source being down is an answer rather than an error: a tool
that raises tells the model it did something wrong, and it did not.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import httpx

from harry.sdk import Context, Registry

FORECAST = 'https://api.open-meteo.com/v1/forecast'

TIMEOUT = 5.0
"""Seconds. The morning page's build is already the call that blocks, and a hanging weather
lookup adds to it directly."""

DAILY = 'weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max'
"""`precipitation_probability_max`, not `_mean`. They are different numbers for the same day
and the page answers "will I need a coat" — the chance it rains at all, not the average
across the hours."""

HOURLY = 'temperature_2m,weather_code'
"""The shape of the day, on the same request as the summary of it. One endpoint answers both,
so asking twice would be a second call for something the first could have carried.

`weather_code` as well as the temperature, because a strip of numbers is half a forecast:
nine degrees under a sun and nine under a thundercloud are different mornings. Claude reads
both through `weather_forecast`."""

FIRST_HOUR, LAST_HOUR = 6, 22
"""The hours worth printing. Before six nobody is reading and after ten nobody is going out,
and a strip of twenty-four numbers is a table rather than a glance."""

WORDS = {
    0: 'clear',
    1: 'mainly clear',
    2: 'partly cloudy',
    3: 'overcast',
    45: 'fog',
    48: 'fog',
    51: 'drizzle',
    53: 'drizzle',
    55: 'drizzle',
    56: 'freezing drizzle',
    57: 'freezing drizzle',
    61: 'rain',
    63: 'rain',
    65: 'rain',
    66: 'freezing rain',
    67: 'freezing rain',
    71: 'snow',
    73: 'snow',
    75: 'snow',
    77: 'snow grains',
    80: 'showers',
    81: 'showers',
    82: 'showers',
    85: 'snow showers',
    86: 'snow showers',
    95: 'thunderstorm',
    96: 'thunderstorm with hail',
    99: 'thunderstorm with hail',
}
"""WMO code to the word that goes on the page.

A table, not a judgement: every code has exactly one answer and the answer never depends on
the situation. Intensity is dropped — "moderate rain" and "heavy rain" are the same decision
about a coat, and the shorter line is the readable one.
"""


class Weather:
    """One place, one day, one call."""

    def __init__(self, latitude: float, longitude: float, timezone: str, place: str, log: logging.Logger) -> None:
        self._where = {'latitude': latitude, 'longitude': longitude, 'timezone': timezone}
        self.place = place
        self._log = log

    def today(self) -> dict | None:
        """The four facts, or None. What the morning page calls.

        None rather than an exception, because one dead source must cost one section of the
        page and nothing else.
        """
        answer = self.forecast()
        if not answer['available']:
            return None
        return {key: answer[key] for key in ('summary', 'high', 'low', 'rain_chance')}

    def forecast(self) -> dict:
        """The same lookup, shaped for a caller that wants to be told why.

        `available` is on both answers, so a reader checks one key rather than inferring
        from which keys are missing.
        """
        try:
            response = httpx.get(
                FORECAST,
                timeout=TIMEOUT,
                params={**self._where, 'daily': DAILY, 'hourly': HOURLY, 'forecast_days': 1},
            )
            response.raise_for_status()
            return {'available': True, 'place': self.place, **self._read(response.json())}
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as error:
            why = _why(error)
            self._log.warning('no forecast for %s: %s', self.place, why)
            return {'available': False, 'place': self.place, 'why': why}

    def _read(self, answered: dict) -> dict:
        """Today's row, rounded. The page is read at arm's length over coffee, so 21.5 and
        59.0% are noise on paper."""
        daily = answered['daily']
        code = int(daily['weather_code'][0])
        word = WORDS.get(code)
        if word is None:
            # The numbers are still true and still useful. A word invented for a condition
            # this table does not know would be neither.
            self._log.warning('no word for WMO code %s; the page will carry the numbers only', code)
        return {
            'summary': word,
            'high': round(daily['temperature_2m_max'][0]),
            'low': round(daily['temperature_2m_min'][0]),
            'rain_chance': round(daily['precipitation_probability_max'][0]),
            'hours': self._hours(answered.get('hourly') or {}),
        }

    def _hours(self, hourly: Mapping[str, Any]) -> list[dict]:
        """The day's temperatures between `FIRST_HOUR` and `LAST_HOUR`, or an empty list.

        Never raises, which is the point of it. The day itself arrived in the same response,
        and a strip that could not be read must cost the strip rather than the whole panel —
        so a missing block, a short array or an unparseable entry each drop out quietly and
        leave `available` true.
        """
        times = hourly.get('time') or []
        degrees = hourly.get('temperature_2m') or []
        if not times or not degrees:
            self._log.info('no hourly temperatures for %s; the page carries the day without its strip', self.place)
            return []
        # An hourly block with no codes is still a strip worth drawing — the numbers are the
        # part that cannot be guessed from the day's own summary. But it is said out loud: a
        # single unrecognised code already warns, and the larger loss going quiet is how a
        # strip of bare numbers arrives for a month and nobody wonders why.
        codes = hourly.get('weather_code') or []
        if len(codes) < len(times):
            self._log.info(
                'the hourly forecast for %s carried %d code(s) for %d hour(s); '
                'those hours draw a temperature and no sky',
                self.place,
                len(codes),
                len(times),
            )
        found: list[dict] = []
        unknown: set[int] = set()
        # `strict=False`: arrays of different lengths are a malformed answer, and the honest
        # response is the part that lines up rather than no strip at all. `codes` is padded so
        # a missing array costs the words and not the readings.
        padded = list(codes) + [None] * max(len(times) - len(codes), 0)
        for stamp, degree, code in zip(times, degrees, padded, strict=False):
            # Open-Meteo's default `timeformat` is iso8601, so a stamp is `2026-09-15T06:00`
            # and characters 11 to 16 are the time. Asking for `unixtime` instead would empty
            # the strip silently, which is why the request never does.
            at = str(stamp)[11:16]
            try:
                hour, reading = int(at[:2]), round(float(degree))
            except (TypeError, ValueError):
                continue
            if FIRST_HOUR <= hour <= LAST_HOUR:
                found.append({'at': at, 'temperature': reading, 'summary': self._word(code, unknown)})
        if unknown:
            # Once per answer, not once per hour: a day of the same unrecognised code would
            # otherwise say the same thing seventeen times and bury everything around it.
            self._log.warning(
                'no word for WMO code(s) %s in the hourly forecast; those hours carry the number only',
                ', '.join(str(code) for code in sorted(unknown)),
            )
        return found

    @staticmethod
    def _word(code: object, unknown: set[int]) -> str | None:
        """One hour's sky, from the same table the day uses, remembering what it could not read.

        The same `WORDS` as `_read`, so an hour and the day it belongs to can never disagree
        about what a code means.
        """
        try:
            # pyright: ignore[reportArgumentType] — None and a non-numeric string both land
            # below. A numeric string does not: int("3") is 3, and 3 is a code the table has.
            number = int(code)  # pyright: ignore[reportArgumentType]
        except (TypeError, ValueError):
            return None
        word = WORDS.get(number)
        if word is None:
            unknown.add(number)
        return word


def _why(error: Exception) -> str:
    """What to tell somebody, from what went wrong. One sentence each, no traceback."""
    if isinstance(error, httpx.TimeoutException):
        return f'open-meteo did not answer within {TIMEOUT:g}s'
    if isinstance(error, httpx.HTTPStatusError):
        return f'open-meteo answered {error.response.status_code}'
    if isinstance(error, httpx.HTTPError):
        return 'open-meteo could not be reached'
    return 'open-meteo answered something this connector does not understand'


def register(registry: Registry, context: Context) -> None:
    registry.connector(
        Weather(
            latitude=float(context.config['latitude']),
            longitude=float(context.config['longitude']),
            timezone=str(context.config['timezone']),
            place=str(context.config['place']),
            log=context.log,
        )
    )
