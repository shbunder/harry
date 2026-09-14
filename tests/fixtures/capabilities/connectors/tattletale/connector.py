"""Alerts inside register(), which is the one moment there is nowhere to send."""

from harry.sdk import Context, Registry


def register(registry: Registry, context: Context) -> None:
    context.alert('I have nothing to say yet', key='too-early')
    registry.connector(object())
