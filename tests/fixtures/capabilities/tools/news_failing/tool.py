"""Fails on purpose, with the kind of message a tool ought to fail with."""

from harry.sdk import Context, Registry


def register(registry: Registry, context: Context) -> None:
    @registry.tool
    def news_failing(since: str = 'today') -> list[dict]:
        raise ValueError('no articles since 05:00, try since=yesterday')
