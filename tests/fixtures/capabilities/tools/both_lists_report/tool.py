"""One connector required, one optional, and a report of what arrived."""

from harry.sdk import Context, Registry


def register(registry: Registry, context: Context) -> None:
    reached = sorted(context.connectors)

    @registry.tool
    def both_lists_report() -> dict:
        return {'reached': reached}
