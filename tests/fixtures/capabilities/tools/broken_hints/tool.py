"""Fine as Python. The declaration beside it is what fails, and only at publish time."""

from harry.sdk import Context, Registry


def register(registry: Registry, context: Context) -> None:
    @registry.tool
    def broken_hints() -> str:
        return 'never reachable'
