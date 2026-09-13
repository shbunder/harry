"""Same cron expression as ticker, nine hours earlier."""

from harry.sdk import Context, Registry


def register(registry: Registry, context: Context) -> None:
    @registry.job
    def tokyo() -> None:
        return None
