"""One verb: what is already on the tablet.

Separate from the push because checking and sending are different questions, and this one is
read-only — which is how a client can allow it while gating the tool that writes to a device.

**This one takes a folder and the push does not, and that asymmetry is deliberate.** Reading a
folder cannot do any harm. Pushing carries the delete that replaces a document of the same
name, so which folder that runs in is not a decision to hand a model: the connector's setting
decides, and a caller with a folder of its own — the morning page — names it in its own
configuration where a person chose it.
"""

from harry.sdk import Context, Registry


def register(registry: Registry, context: Context) -> None:
    tablet = context.connectors['remarkable']

    @registry.tool
    def remarkable_list_documents(limit: int | None = None, folder: str | None = None) -> list[dict]:
        # The cap is the connector's — one number, in the place that enforces it. A default
        # spelled again here would be a second owner, and the two disagree eventually.
        return tablet.documents(folder=folder) if limit is None else tablet.documents(limit, folder)
