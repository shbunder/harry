"""Harry's HTTP app, and the one route core owns.

`/health` answers what loaded, what did not, and why. That endpoint is not bookkeeping:
skipping a broken capability is only safe because the skip is visible, and without this
the difference between Harry working and Harry silently three-quarters working is a log
file nobody opens.

**A skipped capability is not an error status.** Harry running with four of five is Harry
running, and returning 503 for it would train whoever is watching to ignore the number.
The response says which one is missing and why; deciding whether that matters is a
person's job, or eventually the job that sends it to Slack.

Capabilities load once, at start-up, in the lifespan below — not at import, so that
importing this module to inspect the app does not walk the disk and run other people's
code. Harry restarts to pick up a change, the way Home Assistant does.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request

from harry import __version__
from harry.loader import load


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Find and load every capability, once, before the first request is served."""
    app.state.catalogue = load()
    yield


def build_app() -> FastAPI:
    """Harry's app. One function so a test gets a real one rather than a stand-in."""
    app = FastAPI(title='Harry', version=__version__, lifespan=lifespan)

    @app.get('/health')
    async def health(request: Request) -> dict[str, Any]:
        """What Harry can do right now, and what it cannot.

        Every capability it found, with its kind, whether it loaded, and — for each one
        that did not — the sentence explaining why. No setting values appear here, secret
        or otherwise: this says what is running, and a configuration dump is a different
        thing with a different audience.
        """
        return request.app.state.catalogue.as_health()

    return app


app = build_app()
