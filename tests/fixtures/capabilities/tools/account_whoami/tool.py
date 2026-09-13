"""Asks for the principal, which Harry fills in from the token rather than the caller."""

from harry.sdk import Context, Principal, Registry


def register(registry: Registry, context: Context) -> None:
    @registry.tool
    def account_whoami(principal: Principal) -> dict:
        return {'id': principal.id, 'name': principal.name}
