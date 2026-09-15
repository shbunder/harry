"""Find every capability on disk, read it, and run it — each inside its own try/except.

This is the code every capability depends on, and the property that decides whether the
design is usable is not discovery. It is what happens when one of them is broken: **a
half-written capability is logged and stepped over, never fatal.** Without that, the first
thing you leave unfinished stops the morning page rendering at all, and the honest
response is to stop developing in `.harry/` — which is the whole product.

Nothing here knows the name of any capability. Adding one is a folder; there is no import
list to extend and no `if name ==` to find.

The order of the work:

1. **Discover.** Walk the roots in order and collect folders. A later root replaces an
   earlier capability of the same name and kind — the swap mechanism, and the reason
   `capability_roots()` is a list. The replaced one is recorded, never loaded, and said
   out loud: silently replacing code is worse than replacing it loudly.
2. **Load, connectors first.** A tool or a job naming a connector in `requires:` can only
   be told its connector is missing once the connectors have had their turn.

Every reason ends up in `/health`, so every reason is written for somebody who is not
debugging this — **Explainable**.
"""

from __future__ import annotations

import importlib.util
import logging
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path
from types import ModuleType
from typing import Any

from harry.boundary import forbidden_imports
from harry.config import capability_roots, read_capability_config
from harry.declaration import BY_NAME, KINDS, Kind, Malformed, read_body, read_frontmatter
from harry.registry import LOADED, Capability, Catalogue, Connectors, Context, Registry

LOG = logging.getLogger('harry.loader')


class Skip(Exception):
    """This capability is not going to run, and here is the sentence explaining why.

    Separate from an unexpected failure only in how the reason reads: a `Skip` says what
    is wrong in plain words, an unexpected exception gets its type and message. Both end
    up in the same place, and both cost exactly this one capability.
    """


def load(roots: Sequence[Path] | None = None, alerts: Any = None) -> Catalogue:
    """Everything Harry can do, as far as this machine is concerned.

    `roots` is for tests and for anything that wants to load a tree that is not this
    instance's. Left out, it is whatever `capability_roots()` resolves to.

    `alerts` is handed to every capability so it can report its own failures. It arrives
    before its sinks do, because a sink is itself a capability and has to load first — see
    `Alerts.attach`.
    """
    searched = list(roots) if roots is not None else capability_roots()
    catalogue = Catalogue(roots=searched)
    for kind in KINDS:
        for capability in _winners(kind, searched, catalogue):
            _load_one(capability, catalogue, alerts)
    _say_what_happened(catalogue)
    return catalogue


def _winners(kind: Kind, roots: Iterable[Path], catalogue: Catalogue) -> list[Capability]:
    """One folder per name, later root wins, losers recorded rather than loaded.

    Not loading the loser is the point: running code that is about to be discarded means
    its side effects happen and its failures are reported, for something that is not the
    version anybody is using.
    """
    chosen: dict[str, Capability] = {}
    for root in roots:
        directory = root / kind.folder
        if not directory.is_dir():
            continue
        for folder in sorted(path for path in directory.iterdir() if path.is_dir()):
            earlier = chosen.get(folder.name)
            if earlier is not None:
                earlier.shadowed_by = folder
                LOG.warning('%s: replaced by %s, shadowing %s', folder.name, folder, earlier.folder)
                catalogue.skip(earlier, f'replaced by {folder}')
            chosen[folder.name] = Capability(name=folder.name, kind=kind.singular, folder=folder, root=root)
    return list(chosen.values())


def _load_one(capability: Capability, catalogue: Catalogue, alerts: Any = None) -> None:
    """One capability, start to finish, inside one try/except.

    The `except Exception` is deliberate and is the rule this module exists for. A
    capability can fail in any way a piece of Python can fail — a missing dependency, a
    typo, a client that dials out at import — and every one of them must cost exactly
    itself.
    """
    kind = BY_NAME[capability.kind]
    try:
        fields, body = _declaration(capability, kind)
        config = _settings(capability, fields)
        connectors = _connectors_for(fields, catalogue)
        # Built before anything that could fail with a credential in its message, because
        # the Context is what knows which values are secret and scrubs them.
        capability.context = Context(
            name=capability.name,
            kind=capability.kind,
            folder=capability.folder,
            declaration=fields,
            body=body,
            config=config,
            log=logging.getLogger(f'harry.capability.{capability.name}'),
            alerts=alerts,
            connectors=connectors,
        )
        _register(capability, kind)
    except Skip as skip:
        _record_skip(catalogue, capability, str(skip))
    except Exception as error:  # noqa: BLE001 — the whole point: one failure, one capability
        _record_skip(catalogue, capability, f'{type(error).__name__}: {error}')
    else:
        catalogue.add(capability)
        LOG.info('%s %s loaded from %s', capability.kind, capability.name, capability.folder)


def _record_skip(catalogue: Catalogue, capability: Capability, reason: str) -> None:
    catalogue.skip(capability, reason)
    LOG.warning('%s %s skipped: %s', capability.kind, capability.name, capability.reason)


def _declaration(capability: Capability, kind: Kind) -> tuple[dict[str, Any], str]:
    """The frontmatter and the body, or a reason this folder is not a capability."""
    path = capability.folder / kind.declaration
    if not path.is_file():
        raise Skip(f'no {kind.declaration}, so nothing here is loaded')

    try:
        fields = read_frontmatter(path)
    except Malformed as bad:
        # Re-raised as a skip so the reason is the sentence and not `Malformed: <sentence>`.
        # Whoever reads it in /health wants the fault, not the class name.
        raise Skip(str(bad)) from bad
    declared = str(fields.get('name', ''))
    if declared != capability.name:
        raise Skip(f'its declaration is named {declared!r} but the folder is {capability.name!r}')
    if not fields.get('enabled'):
        raise Skip('disabled in its declaration')
    return fields, read_body(path)


def _settings(capability: Capability, fields: dict[str, Any]) -> dict[str, Any]:
    """This capability's settings, and a refusal to start it without the required ones.

    Absent configuration disables one capability and says which setting is missing. It
    does not crash, and — the part that matters — it does not pretend to work and fail at
    06:30 with a stack trace from inside a client library.
    """
    schema = fields.get('config') or {}
    config = read_capability_config(capability.folder, capability.name, schema)
    missing = sorted(name for name, spec in schema.items() if spec.get('required') and not config.get(name))
    if len(missing) == 1:
        raise Skip(f'required setting {missing[0]} is not set')
    if missing:
        # Spelled out rather than comma-joined: this sentence is read by a person, in Slack,
        # on a phone. "required settings bot_token, channel is not set" is not a sentence.
        named = f'{", ".join(missing[:-1])} and {missing[-1]}'
        raise Skip(f'required settings {named} are not set')
    return config


def _connectors_for(fields: dict[str, Any], catalogue: Catalogue) -> Connectors:
    """What `requires:` and `optional:` named, resolved to what those connectors registered.

    One resolution rather than two: the same walk decides whether this capability may load
    at all and what it is handed. A tool whose required connector did not load would
    otherwise register, look healthy, and fail on its first call — a worse version of the
    same outcome, arriving later and somewhere less obvious.

    **The two lists answer one question:** if this connector is missing, is there still
    something worth doing? `requires:` says no and the capability is skipped. `optional:`
    says yes and the capability loads without it, finding nothing under that name in
    `context.connectors`. The morning page is why: a lapsed calendar password should cost
    the agenda column, not the whole page.
    """
    wanted = [str(name) for name in fields.get('requires') or []]

    missing = sorted(
        name for name in wanted if (found := catalogue.get('connector', name)) is None or found.status != LOADED
    )
    if missing:
        raise Skip(f'needs {", ".join(missing)}, which did not load')

    handed = {name: catalogue.get('connector', name) for name in wanted}
    empty = sorted(name for name, found in handed.items() if found is None or found.target is None)
    if empty:
        # A connector with nothing to hand over is refused here rather than left out of the
        # mapping, because the alternative is `KeyError: 'slack'` in /health — in front of
        # somebody who is not debugging.
        raise Skip(f'needs {", ".join(empty)}, which registered nothing to use')

    reached = {name: found.target for name, found in handed.items() if found is not None}

    # Whatever an optional connector turns out to be — absent, skipped, or loaded but
    # registering nothing — the answer here is the same: leave it out. A capability that
    # declared it optional has already said it can manage, and the way it finds out is that
    # the name is not there.
    for name in (str(name) for name in fields.get('optional') or []):
        found = catalogue.get('connector', name)
        # `target is not None` is the whole question, and it is one question rather than two:
        # a connector that was never configured has no entry, one that raised on import has
        # no target, and one that loaded and registered nothing has no target either. Adding
        # a status check beside it reads as thorough and tests as redundant.
        if found is not None and found.target is not None:
            reached[name] = found.target

    return Connectors(reached)


def _register(capability: Capability, kind: Kind) -> None:
    """Run the capability's own code, if it has any.

    A folder with no Python is a whole capability for a connector or a job: a
    `trigger: claude` job is one markdown file, because Claude runs the half that needs a
    mind. **A tool is the exception** — a tool with nothing behind it is one Claude will
    pick and then fail on, and that failure reads as a broken tool rather than an
    unfinished folder.
    """
    module_path = capability.folder / kind.module
    if not module_path.is_file():
        if capability.kind == 'tool':
            raise Skip(f'no {kind.module}, so there is nothing for this tool to call')
        return

    findings = forbidden_imports(capability.folder)
    if findings:
        raise Skip(f'reaches past harry.sdk — {findings[0]}')

    module = _import(capability, module_path)
    register = getattr(module, 'register', None)
    if not callable(register):
        raise Skip(f'{kind.module} has no register(registry, context)')

    register(Registry(capability), capability.context)


def _import(capability: Capability, path: Path) -> ModuleType:
    """Load a capability's entry module from its path, as a package.

    A package rather than a plain module so `from .client import fetch` works — a
    capability is a folder, and the code in it is usually more than one file.

    The module name is synthetic and carries the kind and the folder name, so a traceback
    says which capability it came from. Anything already cached under that name is dropped
    first: without it, a second load would re-use a stale `…icloud.client` from the first.
    """
    name = f'harry_capabilities.{capability.kind}.{capability.name}'
    for cached in [key for key in sys.modules if key == name or key.startswith(f'{name}.')]:
        del sys.modules[cached]

    spec = importlib.util.spec_from_file_location(name, path, submodule_search_locations=[str(path.parent)])
    if spec is None or spec.loader is None:  # pragma: no cover — a readable .py always gives a spec
        raise Skip(f'{path.name} could not be loaded as Python')

    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        del sys.modules[name]
        raise
    return module


def _say_what_happened(catalogue: Catalogue) -> None:
    """One line at start-up, so a restart shows the damage without anyone asking.

    A fresh install with nothing in `.harry/` says so rather than staying silent — an
    empty Harry and a Harry that failed to find its capabilities look identical otherwise.
    """
    if not len(catalogue):
        LOG.info('no capabilities found in %s', ', '.join(str(root) for root in catalogue.roots) or 'any root')
        return
    loaded = len(catalogue.loaded)
    LOG.info(
        '%d %s loaded, %d skipped', loaded, 'capability' if loaded == 1 else 'capabilities', len(catalogue.skipped)
    )
