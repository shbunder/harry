"""Loads whether or not `weather` did, and says which way it went."""

from harry.sdk import Context, Registry


def register(registry: Registry, context: Context) -> None:
    reached = sorted(context.connectors)

    @registry.tool
    def hopeful_report() -> dict:
        return {'reached': reached}
