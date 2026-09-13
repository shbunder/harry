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
from harry.declaration import BY_NAME, KINDS, Kind, read_body, read_frontmatter
from harry.registry import LOADED, Capability, Catalogue, Context, Registry

LOG = logging.getLogger('harry.loader')

REDACTED = '[redacted]'


class Skip(Exception):
    """This capability is not going to run, and here is the sentence explaining why.

    Separate from an unexpected failure only in how the reason reads: a `Skip` says what
    is wrong in plain words, an unexpected exception gets its type and message. Both end
    up in the same place, and both cost exactly this one capability.
    """


def load(roots: Sequence[Path] | None = None) -> Catalogue:
    """Everything Harry can do, as far as this machine is concerned.

    `roots` is for tests and for anything that wants to load a tree that is not this
    instance's. Left out, it is whatever `capability_roots()` resolves to.
    """
    searched = list(roots) if roots is not None else capability_roots()
    catalogue = Catalogue(roots=searched)
    for kind in KINDS:
        for capability in _winners(kind, searched, catalogue):
            _load_one(capability, catalogue)
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


def _load_one(capability: Capability, catalogue: Catalogue) -> None:
    """One capability, start to finish, inside one try/except.

    The `except Exception` is deliberate and is the rule this module exists for. A
    capability can fail in any way a piece of Python can fail — a missing dependency, a
    typo, a client that dials out at import — and every one of them must cost exactly
    itself.
    """
    kind = BY_NAME[capability.kind]
    secrets: list[str] = []
    try:
        fields, body = _declaration(capability, kind)
        config = _settings(capability, fields)
        secrets = _secret_values(fields, config)
        _check_requirements(capability, fields, catalogue)
        _register(capability, kind, fields, body, config)
    except Skip as skip:
        _record_skip(catalogue, capability, str(skip), secrets)
    except Exception as error:  # noqa: BLE001 — the whole point: one failure, one capability
        _record_skip(catalogue, capability, f'{type(error).__name__}: {error}', secrets)
    else:
        catalogue.add(capability)
        LOG.info('%s %s loaded from %s', capability.kind, capability.name, capability.folder)


def _record_skip(catalogue: Catalogue, capability: Capability, reason: str, secrets: Iterable[str]) -> None:
    reason = _redact(reason, secrets)
    LOG.warning('%s %s skipped: %s', capability.kind, capability.name, reason)
    catalogue.skip(capability, reason)


def _declaration(capability: Capability, kind: Kind) -> tuple[dict[str, Any], str]:
    """The frontmatter and the body, or a reason this folder is not a capability."""
    path = capability.folder / kind.declaration
    if not path.is_file():
        raise Skip(f'no {kind.declaration}, so nothing here is loaded')

    fields = read_frontmatter(path)
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
    if missing:
        setting = 'setting' if len(missing) == 1 else 'settings'
        raise Skip(f'required {setting} {", ".join(missing)} is not set')
    return config


def _secret_values(fields: dict[str, Any], config: dict[str, Any]) -> list[str]:
    """Every resolved value this capability declared `secret: true`.

    Collected so they can be scrubbed out of anything that reaches `/health` or the log.
    The message that goes wrong is never the one somebody was careful with — it is
    `raise ValueError(f'the service rejected {token}')`, written in a hurry.
    """
    schema = fields.get('config') or {}
    return [str(config[name]) for name, spec in schema.items() if spec.get('secret') and config.get(name)]


def _redact(text: str, secrets: Iterable[str]) -> str:
    for secret in secrets:
        text = text.replace(secret, REDACTED)
    return text


def _check_requirements(capability: Capability, fields: dict[str, Any], catalogue: Catalogue) -> None:
    """A tool or a job whose connector did not load does not load either.

    It would otherwise register, look healthy, and fail on its first call — which is a
    worse version of the same outcome, arriving later and somewhere less obvious.
    """
    unmet = [
        str(name)
        for name in fields.get('requires') or []
        if (connector := catalogue.get('connector', str(name))) is None or connector.status != LOADED
    ]
    if unmet:
        raise Skip(f'needs {", ".join(sorted(unmet))}, which did not load')


def _register(capability: Capability, kind: Kind, fields: dict[str, Any], body: str, config: dict[str, Any]) -> None:
    """Run the capability's own code, if it has any.

    A folder with no Python is a whole capability: a `trigger: claude` job is one markdown
    file, because Claude runs the half of it that needs a mind.
    """
    module_path = capability.folder / kind.module
    if not module_path.is_file():
        return

    findings = forbidden_imports(capability.folder)
    if findings:
        raise Skip(f'reaches past harry.sdk — {findings[0]}')

    module = _import(capability, module_path)
    register = getattr(module, 'register', None)
    if not callable(register):
        raise Skip(f'{kind.module} has no register(registry, context)')

    register(
        Registry(capability),
        Context(
            name=capability.name,
            kind=capability.kind,
            folder=capability.folder,
            declaration=fields,
            body=body,
            config=config,
            log=logging.getLogger(f'harry.capability.{capability.name}'),
        ),
    )


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
