"""Run Harry: `python -m harry [--reload]`.

The port lives in exactly one place — `config.py`, fed by `.env` and `.env.local`. The
Makefile does not pass `--port` and neither does the Dockerfile, so a worktree that sets
`HARRY_PORT=7431` in its own `.env.local` is served on 7431 by every way of starting it.

The alternative — make reading the dotenv files to build a `--port` flag — is how the
setting ends up with two owners that disagree. It also breaks on the first value
containing a `#`, which `SLACK_DEFAULT_CHANNEL=#harry` already is.
"""

from __future__ import annotations

import argparse
import sys

from harry.config import get_settings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='harry', description='Run Harry.')
    parser.add_argument('--reload', action='store_true', help='restart on a code change')
    args = parser.parse_args(argv)

    settings = get_settings()

    # Imported here rather than at module scope so `--help` works without uvicorn, and so
    # a missing dependency names itself instead of failing at import of the package.
    import uvicorn

    # A factory, not a module attribute: the app cannot exist until the capabilities are
    # loaded, because the MCP server publishes them and routes cannot appear after the app
    # is serving. `--reload` re-imports and calls this again, which is what a restart is.
    uvicorn.run(
        'harry.main:build_app',
        factory=True,
        host=settings.host,
        port=settings.port,
        reload=args.reload,
        log_level=settings.log_level.lower(),
    )
    return 0


if __name__ == '__main__':
    sys.exit(main())
