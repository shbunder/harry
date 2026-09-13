"""Registers the Context it was handed, so a test can see what the loader put in it."""

from harry.sdk import Context, Registry


def register(registry: Registry, context: Context) -> None:
    registry.connector(context)
