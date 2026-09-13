"""Puts its own credential in an exception message, which is what people actually do."""

from harry.sdk import Context, Registry


def register(registry: Registry, context: Context) -> None:
    raise ValueError(f'the service rejected {context.config["api_key"]}')
