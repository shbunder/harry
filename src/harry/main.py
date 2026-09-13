"""Harry's HTTP app: `/health`, and the MCP server at `/mcp`.

`/health` answers what loaded, what did not, and why. That endpoint is not bookkeeping:
skipping a broken capability is only safe because the skip is visible, and without this the
difference between Harry working and Harry silently three-quarters working is a log file
nobody opens.

**A skipped capability is not an error status.** Harry running with four of five is Harry
running, and returning 503 for it would train whoever is watching to ignore the number. The
response says which one is missing and why; deciding whether that matters is a person's job,
or eventually the job that sends it to Slack.

**`build_app()` is a factory, and nothing here is built at import.** Capabilities have to be
loaded before the app exists, because the MCP server publishes them as routes and a route
cannot appear after the app is serving. So `python -m harry` starts uvicorn with
`factory=True` rather than pointing at a module-level `app`, and importing this module
still walks no directories and runs nobody's code.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request

from harry import __version__, config
from harry.alerts import Alerts, report_start_up
from harry.loader import load
from harry.mcp import build_server
from harry.scheduler import Jobs
from harry.store import Store

MCP_PATH = '/mcp'


def configure_logging() -> None:
    """Make `HARRY_LOG_LEVEL` mean something for Harry's own loggers.

    uvicorn configures its own three loggers and leaves the root logger alone, so without
    this every line Harry logs below WARNING goes to logging's last-resort handler and is
    dropped. This shipped that way for an afternoon: `HARRY_LOG_LEVEL=INFO` was in the
    committed `.env`, `weather loaded` never appeared, and the setting looked applied
    because uvicorn took the same value for its own output.

    `basicConfig` adds a root handler only when there is none — true under uvicorn, false
    under pytest — so this configures the server without pulling the handler out from
    under a test that is capturing records.
    """
    level = config.get_settings().log_level.upper()
    logging.basicConfig(level=level, format='%(levelname)s %(name)s: %(message)s')
    logging.getLogger('harry').setLevel(level)


def build_app() -> FastAPI:
    """Harry, assembled: find the capabilities, publish them, serve them.

    One function so a test gets a real app rather than a stand-in, and so a restart is
    exactly this running again — which is what puts a revealed tool back out of the roster.
    """
    configure_logging()
    catalogue = load()

    # Built after loading and not before: a sink is a capability, so it has to load before
    # it can carry news about anything — including about the capabilities beside it.
    alerts = Alerts.from_catalogue(catalogue)
    report_start_up(catalogue, alerts)

    store = Store(config.get_settings().data_dir / 'jobs.json')
    jobs = Jobs(catalogue, alerts, store)
    mcp_app = build_server(catalogue, store).http_app(path='/')

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # The clock starts here rather than in `build_app`, so building the app to look at
        # it does not put threads behind you.
        jobs.start()
        try:
            # The MCP app brings its own lifespan, and mounting an app does not run it.
            # Without this the session manager never starts and every call to /mcp fails at
            # the first request rather than at start-up, where somebody would see it.
            async with mcp_app.router.lifespan_context(app):
                yield
        finally:
            jobs.stop()

    app = FastAPI(title='Harry', version=__version__, lifespan=lifespan)
    app.state.catalogue = catalogue
    app.state.alerts = alerts
    app.state.store = store
    app.state.jobs = jobs

    @app.get('/health')
    async def health(request: Request) -> dict[str, Any]:
        """What Harry can do right now, and what it cannot.

        Every capability it found, with its kind, whether it loaded, and — for each one
        that did not — the sentence explaining why. No setting values appear here, secret
        or otherwise: this says what is running, and a configuration dump is a different
        thing with a different audience.
        """
        return request.app.state.catalogue.as_health()

    app.mount(MCP_PATH, mcp_app)
    return app
