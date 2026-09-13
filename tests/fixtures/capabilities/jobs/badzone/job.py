"""Fine as Python. The timezone beside it is what fails, and only at scheduling time."""

from harry.sdk import Context, Registry


def register(registry: Registry, context: Context) -> None:
    @registry.job
    def badzone() -> None:
        return None
