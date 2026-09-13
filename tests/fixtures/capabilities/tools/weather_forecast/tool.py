"""One verb: today's forecast."""

from harry.sdk import Context, Registry


def register(registry: Registry, context: Context) -> None:
    @registry.tool
    def weather_forecast(day: str = 'today') -> dict:
        return {'day': day, 'summary': 'grey, as ever'}
