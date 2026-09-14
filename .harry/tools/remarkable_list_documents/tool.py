"""One verb: what is already on the tablet.

Separate from the push because checking and sending are different questions, and this one is
read-only — which is how a client can allow it while gating the tool that writes to a device.
"""

from harry.sdk import Context, Registry


def register(registry: Registry, context: Context) -> None:
    tablet = context.connectors['remarkable']

    @registry.tool
    def remarkable_list_documents(limit: int = 50) -> list[dict]:
        return tablet.documents(limit)
