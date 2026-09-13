"""Async, and asks for the principal. The branch a real connector-backed tool will take."""

import asyncio

from harry.sdk import Context, Principal, Registry


def register(registry: Registry, context: Context) -> None:
    @registry.tool
    async def account_describe(principal: Principal) -> dict:
        await asyncio.sleep(0)
        return {'id': principal.id, 'name': principal.name, 'awaited': True}
