"""One verb: the full text of a story someone chose.

Separate from `news_search` on purpose. The intermediate — which headlines are worth
reading — is the judgement, and a single tool that fetched every article would spend the
context that judgement needs.
"""

from harry.sdk import Context, Registry


def register(registry: Registry, context: Context) -> None:
    news = context.connectors['news']

    @registry.tool
    def news_article(id: str) -> dict:  # noqa: A002
        return news.article(id)
