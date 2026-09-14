"""One verb: what the weather will do today.

The connector does the asking. This exists to say that the forecast is something Claude may
ask for — a choice, written down in the connector's `provides:`.
"""

from harry.sdk import Context, Registry


def register(registry: Registry, context: Context) -> None:
    weather = context.connectors['weather']

    @registry.tool
    def weather_forecast() -> dict:
        return weather.forecast()
