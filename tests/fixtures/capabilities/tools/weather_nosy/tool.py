"""Asks for something it never declared, at registration — which is where a real tool
reaches for its connector, on the first line of register()."""

from harry.sdk import Context, Registry


def register(registry: Registry, context: Context) -> None:
    forecast = context.connectors['weather']

    @registry.tool
    def weather_nosy() -> dict:
        return forecast.today()
