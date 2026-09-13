"""A connector that works."""

from harry.sdk import Context, Registry


class Forecast:
    def __init__(self, place: str) -> None:
        self.place = place

    def today(self) -> dict:
        return {'place': self.place, 'summary': 'grey, as ever'}


def register(registry: Registry, context: Context) -> None:
    registry.connector(Forecast(context.config['place']))
