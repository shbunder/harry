"""One verb: put a line in a channel.

The connector does the talking. This exists to say that posting is something Claude may ask
for — which is a choice, written down in the connector's `provides:`, rather than a
consequence of the connector being able to do it.
"""

from harry.sdk import Context, Registry


def register(registry: Registry, context: Context) -> None:
    slack = context.connectors['slack']

    @registry.tool
    def slack_post(text: str, channel: str | None = None) -> dict:
        return {'channel': slack.send(text, channel=channel), 'posted': text}
