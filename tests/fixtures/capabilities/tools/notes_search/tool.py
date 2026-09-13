"""A deferred tool: out of the roster until somebody searches for it."""

from harry.sdk import Context, Registry


def register(registry: Registry, context: Context) -> None:
    @registry.tool
    def notes_search(query: str, limit: int = 20) -> list[dict]:
        return [{'id': 'note-2026-09-13-groceries', 'matched': query}][:limit]
