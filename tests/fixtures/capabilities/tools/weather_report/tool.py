"""Uses the connector it declared. Imports harry.sdk and nothing else."""

from harry.sdk import Context, Registry


def register(registry: Registry, context: Context) -> None:
    forecast = context.connectors['weather']

    @registry.tool
    def weather_report() -> dict:
        return {'today': forecast.today(), 'declared': sorted(context.connectors)}
