"""Calls the wrong method for its folder, which the registry refuses."""

from harry.sdk import Context, Registry


def register(registry: Registry, context: Context) -> None:
    registry.tool(lambda: 'this is not a connector')
