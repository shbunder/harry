"""Never reached: the loader refuses this before its register can run."""

from harry.sdk import Context, Registry


def register(registry: Registry, context: Context) -> None:
    @registry.tool
    def quiet_report() -> str:
        return context.connectors['quiet']
