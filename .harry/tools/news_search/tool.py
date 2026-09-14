"""One verb: what the news feeds are carrying.

The search half of the pair. It stays separate from `news_article` because choosing among
the headlines is the product — see `.claude/rules/tool-design.md`.
"""

from typing import Literal

from harry.sdk import Context, Registry


def register(registry: Registry, context: Context) -> None:
    news = context.connectors['news']

    @registry.tool
    def news_search(
        query: str | None = None,
        source: str | None = None,
        since: str | None = None,
        limit: int = 20,
        detail: Literal['concise', 'full'] = 'concise',
    ) -> dict:
        return news.search(query=query, source=source, since=since, limit=limit, detail=detail)
