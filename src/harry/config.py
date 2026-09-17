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

import os
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field, SecretStr, field_validator
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
        # `.env` carries every capability's keys too. Core must not fail to start because
        # a capability it has never heard of declared a setting.
        extra='ignore',
        # So `Settings(capabilities_dir=…)` works, not only the aliased name. Without it a
        # field with a `validation_alias` silently ignores its own name at init, and a
        # test constructing one gets the default while looking like it set something.
        populate_by_name=True,
    )

    port: int = 7430
    """Marcel owns 7420 and 7421. A worktree gets its own, set in its `.env.local`."""

    host: str = '0.0.0.0'

    data_dir: Path = Path('/data')
    """SQLite, rendered pages, cached articles, and the De Tijd browser session."""

    api_token: SecretStr = SecretStr('')
    """The MCP bearer token and hook auth. Generate with `openssl rand -hex 32`."""

    public_url: str | None = ''
    """`https://harry.<domain>` — the tunnel hostname. Empty means localhost only."""

    capabilities_dir: Path | None = Field(default=None, validation_alias='HARRY_CAPABILITIES_DIR')
    """Optional directory of out-of-tree capabilities, loaded after this instance's own."""

    capability_settings_dir: Path | None = Field(default=None, validation_alias='HARRY_CAPABILITY_SETTINGS_DIR')
    """Where this machine's `.env.local` for each capability is read from, when it is not
    beside the capability. Laid out like `.harry/`: `<dir>/connectors/icloud/.env.local`.

    **A container is why.** `.dockerignore` keeps every `.env.local` out of the image, so
    the real stack's compose service mounts the checkout's `.harry/` read-only and names the
    mount here. A credential then lives in one file, in its connector's folder, rather than
    a second time under a prefixed name in the root `.env.local`. Empty on a laptop, where
    the file sits beside the capability anyway, and on the dev stack, which keeps its own.
    """

    @field_validator('capabilities_dir', 'capability_settings_dir', 'public_url', mode='before')
    @classmethod
    def _blank_is_unset(cls, value: Any) -> Any:
        """An empty value in a file means unset, and for a path it must mean None.

        `HARRY_CAPABILITIES_DIR=` coerced to `Path('')`, which is `Path('.')` — so an
        unset key would have added the working directory as a capability root and tried
        to load the whole repository as capabilities.
        """
        return None if isinstance(value, str) and not value.strip() else value

    log_level: str = 'INFO'

    timezone: str = Field(default='Europe/Brussels', validation_alias='HARRY_LOCATION_TZ')
    """The scheduler's timezone. 06:30 is a local time, not a UTC one."""

    scheduler_enabled: bool = True
    """Whether this instance runs the clock at all. Off for a second stack on one machine.

    Two Harrys sharing a box would both run the deadline watchdog, and the spare one would
    say "morning-page has not run today" about a morning the real one delivered — which is
    how the channel that carries real failures gets muted. A stack with this off schedules
    nothing and watches nothing, and `/health` says so rather than listing deadlines that
    nobody is checking.
    """

    @property
    def mcp_url(self) -> str:
        """The local address to register Harry at, for a session on this machine.

        Off the machine, a session reaches `public_url` through the tunnel instead.
        Harry never dials out to a model either way — it is called, it does not call.
        """
        return f'http://localhost:{self.port}/mcp'


def env_key(implementation: str, field: str) -> str:
    """The **environment variable** that overrides a capability's setting.

        env_key('icloud', 'app_password')  ->  'HARRY_ICLOUD_APP_PASSWORD'

    Not the name in the capability's own files — there the key is bare (`APP_PASSWORD`),
    because the folder is the namespace. This spelling exists for the one caller that has
    no folders: a container, which injects a flat environment.

    This is the one definition. `scripts/check_capabilities.py` imports it rather than
    reimplementing the rule, so the key the validator prints and the key Harry reads
    cannot drift apart.
    """
    return f'HARRY_{implementation}_{field}'.replace('-', '_').upper()


# Capabilities shipped inside the package. Empty today — every capability lives in the
# instance's own `.harry/`. It exists so the list below has the shape it will need.
BUNDLED_CAPABILITIES = Path(__file__).parent / 'capabilities'


@dataclass(frozen=True)
class Principal:
    """Who is asking.

    One today — the owner, resolved from the single bearer token. It is a parameter on
    everything that could ever be per-person, so that adding a second one is adding a
    token rather than changing every tool signature, every store row and the auth layer
    at once.

    **This is a seam, not a security boundary.** One token resolving to one principal is
    not authentication. A second principal needs a real answer about issuing, rotating and
    scoping tokens, and that answer is not here yet.
    """

    id: str
    name: str


OWNER = Principal(id='owner', name='the owner')


def principal_for_token(token: str) -> Principal | None:
    """The caller behind a bearer token, or None if it is not recognised.

    Today: one token, one principal. The shape is a lookup because that is what it becomes.
    """
    configured = get_settings().api_token.get_secret_value()
    if configured and token == configured:
        return OWNER
    return None


def capability_roots() -> list[Path]:
    """Where capabilities are discovered, in load order. **Later wins on name.**

    1. bundled — shipped inside the package
    2. the instance — `.harry/` in the working directory, which is this repo today
    3. extra — `$HARRY_CAPABILITIES_DIR`, when set

    Later-wins is the swap mechanism and the reason this is a list. An instance drops its
    own `connectors/icloud/` beside a bundled one and takes over, with no fork and no
    patch — the way a Home Assistant `custom_components/` entry shadows a built-in.

    Entry points become a fourth root when there is something to install. The list is what
    makes that additive rather than a rewrite.
    """
    roots = [BUNDLED_CAPABILITIES, Path('.harry')]
    extra = get_settings().capabilities_dir
    if extra:
        roots.append(Path(extra))
    return [root.resolve() for root in roots if root.is_dir()]


def user_data_dir(principal: Principal) -> Path:
    """Where one person's own state lives — under the data volume, never the repository.

    Other people's credentials are not something to commit, and making that a directory
    boundary rather than a rule means it cannot be got wrong by inattention.
    """
    return get_settings().data_dir / 'users' / principal.id


def capability_env_files(folder: Path) -> tuple[Path, Path]:
    """The pair inside a capability's folder, in the order pydantic-settings reads them.

    Same meaning as the root pair, one level down: `.env` is committed and generated from
    the `config:` block, `.env.local` is this machine's and is gitignored. Later wins.
    """
    return (folder / '.env', folder / '.env.local')


def mounted_env_file(folder: Path) -> Path | None:
    """A capability's `.env.local` under `HARRY_CAPABILITY_SETTINGS_DIR`, or None when unset.

    The directory mirrors `.harry/`, so `<root>/connectors/icloud` maps to
    `<dir>/connectors/icloud/.env.local` whichever root the capability was found in.

    **Only `.env.local` is read from there.** The committed `.env` travels in the image with
    the declaration it was generated from, and a second copy out of a checkout on another
    commit could disagree with the code that is actually running.
    """
    directory = get_settings().capability_settings_dir
    if directory is None:
        return None
    return directory / folder.parent.name / folder.name / '.env.local'


def read_capability_config(
    folder: Path,
    implementation: str,
    schema: Mapping[str, Mapping[str, Any]],
    principal: Principal | None = None,
) -> dict[str, Any]:
    """Resolve one capability's settings, highest precedence first.

    1. `HARRY_<IMPLEMENTATION>_<SETTING>` in the real environment — a container injecting
    2. `<data>/users/<principal>/connectors/<name>.env` — this person's, when one is given
    3. `.env.local` under `HARRY_CAPABILITY_SETTINGS_DIR` — this machine, seen from a container
    4. `.env.local` in the capability's folder — this machine
    5. `.env` in the capability's folder — committed, generated from the schema
    6. the `default:` in the schema

    Layer 2 is what makes "whose calendar?" answerable. It lives in the data volume rather
    than the repository, because other people's credentials are not something to commit,
    and a directory boundary cannot be got wrong the way a rule can.

    Layer 3 sits above layer 4 because setting the directory is a deliberate act, and in the
    container it exists for there is never a file at layer 4 — the image carries none.

    Returns only what the schema declares. A key sitting in a file that the capability
    never declared is ignored rather than passed through: it is either a typo or a
    leftover, and silently honouring it is how a setting nobody can find takes effect.
    """
    values: dict[str, Any] = {name: spec.get('default') for name, spec in schema.items() if 'default' in spec}

    sources = list(capability_env_files(folder))
    mounted = mounted_env_file(folder)
    if mounted is not None:
        sources.append(mounted)
    if principal is not None:
        sources.append(user_data_dir(principal) / 'connectors' / f'{implementation}.env')

    for path in sources:
        for key, value in _read_env_file(path).items():
            # An empty value is an unset key, not an override. Otherwise the generated
            # `.env` — which leaves every secret blank — would wipe out the defaults it
            # was generated from, and `ARTICLE_LIMIT=` would resolve to '' rather than 8.
            if key.lower() in schema and value != '':
                values[key.lower()] = value

    for name in schema:
        from_environment = os.environ.get(env_key(implementation, name))
        if from_environment:
            values[name] = from_environment

    return values


def _read_env_file(path: Path) -> dict[str, str]:
    """A dotenv file as a flat mapping. Absent is empty; malformed lines are skipped.

    A leading `export` is stripped, as pydantic's dotenv parser and Docker Compose strip it from
    the root pair. Without that, `export FEEDS=…` was read as a key called `export FEEDS` that no
    capability declares — ignored, so the setting fell back to its default with nothing said.
    """
    if not path.is_file():
        return {}
    found: dict[str, str] = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        # Only when whitespace follows, so `EXPORTED_URL=` stays a key of its own.
        if line[:7] in ('export ', 'export\t'):
            line = line[6:].lstrip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, _, value = line.partition('=')
        found[key.strip()] = value.strip().strip('"\'')
    return found


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """The one instance. Cached so the files are read once per process."""
    return Settings()
