"""One verb: put this on the tablet.

Either a PDF that exists or markdown to render — one tool, because from where Claude sits
those are the same request with different material to hand. That is the consolidation rule:
nothing here is an intermediate worth seeing.
"""

from harry.sdk import Context, Registry


def register(registry: Registry, context: Context) -> None:
    tablet = context.connectors['remarkable']

    @registry.tool
    def remarkable_push_document(name: str, path: str | None = None, markdown: str | None = None) -> dict:
        if path and markdown:
            raise ValueError('pass either path or markdown, not both — a file and some text are different requests')
        if not path and not markdown:
            raise ValueError('pass path, for a PDF that exists, or markdown, to have one rendered')
        if markdown:
            return tablet.push_markdown(markdown, name)
        return tablet.push(path, name)
