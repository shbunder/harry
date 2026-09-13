"""The `.harry/` file format, defined once.

Two things read it. `scripts/check_capabilities.py` validates declarations at the gate,
and `harry.loader` reads them at start-up. Two copies of a format drift, and the way they
drift is that the gate passes something the loader then refuses at 06:30 — which is the
one moment nobody is reading a lint log. So the parsing lives here and both import it,
the same reason `env_key` has one definition.

**Frontmatter is what Harry does** — machine-readable and executed. **The body is what
Claude is told** — stored and served verbatim. Harry never parses it, templates it, or
branches on it; that would be reasoning, and Harry does not reason.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class Malformed(Exception):
    """One declaration that cannot be read. Skipping is the loader's business, not this
    module's — here it is only ever a description of what is wrong with the file."""


@dataclass(frozen=True)
class Kind:
    """One of the three kinds a capability can be.

    Core defines these and nothing else about any capability. A fourth kind is a core
    change, deliberately, because a kind is a contract.
    """

    singular: str
    """How one is spoken about: `connector`."""
    folder: str
    """The directory it lives under: `.harry/connectors/`."""
    declaration: str
    """The file that must be there: `CONNECTOR.md`."""
    module: str
    """The Python the loader runs, when there is any: `connector.py`."""


# In load order, and the order matters: `requires:` on a tool or a job names a connector,
# so connectors have to be up before anything can be told its connector is missing.
KINDS: tuple[Kind, ...] = (
    Kind('connector', 'connectors', 'CONNECTOR.md', 'connector.py'),
    Kind('tool', 'tools', 'TOOL.md', 'tool.py'),
    Kind('job', 'jobs', 'JOB.md', 'job.py'),
)

BY_NAME: dict[str, Kind] = {kind.singular: kind for kind in KINDS}


def read_frontmatter(path: Path) -> dict[str, Any]:
    """The YAML header, or a `Malformed` naming what is wrong with it."""
    text = path.read_text(encoding='utf-8')
    if not text.startswith('---'):
        raise Malformed('no YAML frontmatter — the file must open with `---`')
    _, _, rest = text.partition('---\n')
    block, separator, _ = rest.partition('\n---')
    if not separator:
        raise Malformed('the frontmatter block is never closed with `---`')
    try:
        loaded = yaml.safe_load(block)
    except yaml.YAMLError as error:
        raise Malformed(f'the frontmatter is not valid YAML: {error}') from error
    if not isinstance(loaded, dict):
        raise Malformed('the frontmatter must be a mapping of key to value')
    return loaded


def read_body(path: Path) -> str:
    """Everything after the closing `---`.

    Split on `\\n---` rather than `---`: the opening delimiter is at offset 0 with no
    newline before it, so the first match is always the closing one. An earlier version
    partitioned twice and returned the empty string for every well-formed file — which
    looked like every body being empty rather than like a bug.
    """
    return path.read_text(encoding='utf-8').partition('\n---')[2].strip()
