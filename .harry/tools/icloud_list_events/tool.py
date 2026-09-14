"""One verb: what is on for a day.

`icloud_list_events(day)` rather than a CalDAV report — the caller wants their day, not a
protocol. That distinction is the one `.claude/rules/tool-design.md` uses as its example.
"""

from harry.sdk import Context, Registry


def register(registry: Registry, context: Context) -> None:
    calendar = context.connectors['icloud']

    @registry.tool
    def icloud_list_events(day: str | None = None) -> list[dict]:
        return calendar.today() if day is None else calendar.on(day)
