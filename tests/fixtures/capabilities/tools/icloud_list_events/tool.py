"""Never registers in the tests that use it: its connector has no credential."""

from harry.sdk import Context, Registry


def register(registry: Registry, context: Context) -> None:
    @registry.tool
    def icloud_list_events(day: str) -> list:
        return []
