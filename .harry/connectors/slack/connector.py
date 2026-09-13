"""Slack, one way: Harry says something went wrong and a person reads it.

`chat.postMessage` over HTTPS with a bot token. Not `slack-bolt` — that is the two-way app
framework, and none of it is needed to post a line. What is needed is a timeout and an
error that says which Slack error code came back.
"""

from __future__ import annotations

import logging

import httpx

from harry.sdk import Context, Registry

POST_MESSAGE = 'https://slack.com/api/chat.postMessage'

TIMEOUT = 5.0
"""Seconds. Alerts are sent while Harry is starting, and a socket that hangs with no
ceiling holds up the restart somebody is watching."""

WHAT_TO_DO = {
    'not_in_channel': 'invite the bot to {channel} (/invite @Harry in that channel), then try again',
    'channel_not_found': 'check the channel — {channel} is not one this bot can see. A private channel needs the bot invited before it exists to the bot',
    'invalid_auth': 'the bot token was revoked or rotated. Reinstall the Slack app and put the new token in .env.local',
}
"""Slack's code against the fix, which is the runbook beside this file with one caller.

A lookup table, not Harry deciding anything: each of these has exactly one answer and the
answer never depends on the situation. The code alone sends somebody to a search engine;
the sentence is what they actually needed."""


class Slack:
    """A bot token, a channel, and one verb."""

    def __init__(self, token: str, channel: str, log: logging.Logger) -> None:
        self._token = token
        self._channel = channel
        self._log = log

    def send(self, message: str, channel: str | None = None) -> str:
        """Post one line, or raise saying why not. Returns the channel it went to.

        Raising rather than swallowing is the contract `registry.alerts` asks for: a sink
        that returns quietly on a failure makes a fault nobody heard about look exactly
        like one that was reported.

        `channel` is optional because the alert path never passes one — deciding where a
        failure belongs is judgement, and Harry does not do judgement.
        """
        where = channel or self._channel
        response = httpx.post(
            POST_MESSAGE,
            timeout=TIMEOUT,
            headers={'Authorization': f'Bearer {self._token}'},
            json={'channel': where, 'text': message},
        )
        self._check(response, where)
        self._log.debug('told %s', where)
        return where

    def _check(self, response: httpx.Response, channel: str) -> None:
        """Slack's error code, and nothing else from the response.

        **Never the body.** Slack echoes parts of a rejected request back, and the request
        carried the bot token — so quoting the response is how a credential reaches a log
        line. The code is the part that tells you what to do, and the runbook beside this
        file lists them.
        """
        try:
            answered = response.json()
        except ValueError:
            answered = {}

        if not isinstance(answered, dict) or not answered.get('ok'):
            code = answered.get('error') if isinstance(answered, dict) else None
            said = code or f'HTTP {response.status_code}'
            advice = WHAT_TO_DO.get(str(code), '').format(channel=channel)
            raise RuntimeError(f'slack refused the message: {said}' + (f' — {advice}' if advice else ''))


def register(registry: Registry, context: Context) -> None:
    slack = Slack(str(context.config['bot_token']), str(context.config['channel']), context.log)
    registry.connector(slack)
    registry.alerts(slack.send)
