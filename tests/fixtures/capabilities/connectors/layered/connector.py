"""Imports a sibling module, the way a real connector keeps its client separate."""

from harry.sdk import Context, Registry

from .client import Client


def register(registry: Registry, context: Context) -> None:
    registry.connector(Client())
