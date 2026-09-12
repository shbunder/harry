"""Every setting Harry has, declared once and typed.

Nothing else in Harry reads the environment. A stray `os.getenv` is a setting nobody
knows exists, which cannot be reviewed, containerised, or turned off at 06:30 on a
Tuesday — see `.claude/rules/secrets-and-config.md`.

## The two files

Settings are read from two files, and the split is deliberate:

- **`.env`** is committed. It lists every key with its working default and leaves every
  secret empty. It is the documentation of what Harry can be configured with, and it is
  only useful if it is exhaustive. Adding a key there is how every machine learns the
  setting exists.
- **`.env.local`** is gitignored and belongs to one machine. The real secrets, plus
  anything that differs here: a port, a data directory, a browser you want headed.

Highest precedence first:

1. a real environment variable — `HARRY_PORT=7431 make serve`
2. `.env.local`
3. `.env`

That order is what `env_file` below produces: pydantic-settings reads the files left to
right and a later file wins, and a real environment variable outranks both.

## Why there are no `export` prefixes anywhere

In the repo this was adapted from, `make` loaded both files with `-include` and every key
in both had to carry an `export` prefix — because make's `export` puts the value into the
*process environment*, which outranks any dotenv file. A key exported empty in the
committed file and set without `export` in the machine's file resolved to empty, silently,
and the arrangement needed a paragraph of documentation to be survivable.

Harry's Makefile does not load either file. This module is the only reader, so the order
above is simply what it does, and `tests/test_config.py` makes it fail if that changes.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# Left to right, later wins. This tuple is the whole precedence story.
#
# Relative, so they resolve against the working directory — which is what makes a
# worktree work at all. A worktree shares the primary checkout's virtual environment, so
# anchoring these to the installed package would point every worktree at the *primary*
# tree's files and its `.env.local` would be read by nothing, while looking correct.
# Every make target runs from the tree it belongs to, and the container's workdir is
# `/app`, so in practice this always resolves to the root of whichever Harry you started.
ENV_FILES = (Path('.env'), Path('.env.local'))


class Settings(BaseSettings):
    """Harry's core settings. A module declares its own and reads the same two files."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILES,
        env_file_encoding='utf-8',
        env_prefix='HARRY_',
        # `.env` carries every module's keys too. Core must not fail to start because a
        # module it has never heard of declared a setting.
        extra='ignore',
    )

    port: int = 7430
    """Marcel owns 7420 and 7421. A worktree gets its own, set in its `.env.local`."""

    host: str = '0.0.0.0'

    data_dir: Path = Path('/data')
    """SQLite, rendered pages, cached articles, and the De Tijd browser session."""

    api_token: SecretStr = SecretStr('')
    """The MCP bearer token and hook auth. Generate with `openssl rand -hex 32`."""

    public_url: str = ''
    """`https://harry.<domain>` — the tunnel hostname. Empty means localhost only."""

    capabilities_dir: Path | None = Field(default=None, validation_alias='HARRY_CAPABILITIES_DIR')
    """Optional directory of out-of-tree capabilities, walked alongside `.harry/`."""

    log_level: str = 'INFO'

    timezone: str = Field(default='Europe/Brussels', validation_alias='HARRY_LOCATION_TZ')
    """The scheduler's timezone. 06:30 is a local time, not a UTC one."""

    @property
    def mcp_url(self) -> str:
        """The local address to register Harry at, for a session on this machine.

        Off the machine, a session reaches `public_url` through the tunnel instead.
        Harry never dials out to a model either way — it is called, it does not call.
        """
        return f'http://localhost:{self.port}/mcp'


def env_key(implementation: str, field: str) -> str:
    """The environment variable a capability's setting is read from.

    `HARRY_<IMPLEMENTATION>_<FIELD>` — derived, never chosen. Two connectors can both want
    a field called `api_key` and never collide, and a third party can add one without
    knowing what names are already taken.

        env_key('icloud', 'app_password')  ->  'HARRY_ICLOUD_APP_PASSWORD'

    This is the one definition. `scripts/check_capabilities.py` imports it rather than
    reimplementing the rule, so the key the validator reports and the key Harry reads
    cannot drift apart.
    """
    return f'HARRY_{implementation}_{field}'.replace('-', '_').upper()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """The one instance. Cached so the files are read once per process."""
    return Settings()
