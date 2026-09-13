"""A job with code, which is what `trigger: schedule` usually means."""

from harry.sdk import Context, Registry


def register(registry: Registry, context: Context) -> None:
    @registry.job
    def refresh() -> str:
        return 'refreshed'
