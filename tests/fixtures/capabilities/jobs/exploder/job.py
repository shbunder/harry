"""Fails on purpose, so what a failing job costs is a fact rather than a hope."""

from harry.sdk import Context, Registry


def register(registry: Registry, context: Context) -> None:
    @registry.job
    def exploder() -> None:
        raise ConnectionError('the feed host refused the connection')
