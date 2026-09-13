"""What a capability hands over, and what became of every capability Harry found.

Core's half of the contract. It knows the three kinds and nothing about any individual
capability — no import list, no `if name == …`, no roster of known connectors. That is
the property `.claude/rules/capability-shape.md` exists to protect, and the moment it
stops being true every new capability costs a core edit and a core review.

Three objects, and they are deliberately separate:

- **`Registry`** is what one capability's `register()` is handed. It is scoped to that
  capability, which is why none of its methods take a name.
- **`Context`** is what that capability is told about itself: its folder, its declaration,
  its resolved settings, and a logger of its own.
- **`Catalogue`** is everything Harry found, loaded or not, and it is what `/health`
  serves. A capability that was skipped is in here with its reason — the whole point is
  that a skip is visible rather than silent.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from harry.config import Principal, read_capability_config

LOADED = 'loaded'
SKIPPED = 'skipped'

REDACTED = '[redacted]'


class ContractError(Exception):
    """A capability used the registry in a way its declaration does not support.

    Raised out of `Registry`, caught by the loader like any other failure during
    registration: the capability is skipped and the message becomes its reason.
    """


@dataclass(frozen=True)
class Context:
    """What a capability is handed when it registers.

    `config` is resolved with no principal, because registration happens once, at
    start-up, and is not a call. `config_for()` is for the call that does know whose
    calendar it is: the NUC serves more than one person eventually, and a tool signature
    with no caller in it is the retrofit nobody wants to do later.
    """

    name: str
    kind: str
    folder: Path
    declaration: Mapping[str, Any]
    body: str
    """The declaration's body, verbatim. Harry serves it and never reads it."""
    config: Mapping[str, Any]
    log: logging.Logger

    def config_for(self, principal: Principal) -> dict[str, Any]:
        """The same settings, resolved for one person.

        Their own file under the data volume wins over the instance's, key by key. A
        capability that never asks behaves exactly as it does today.
        """
        schema = self.declaration.get('config') or {}
        return read_capability_config(self.folder, self.name, schema, principal=principal)

    def redact(self, text: str) -> str:
        """This capability's declared secrets, taken out of anything about to be reported.

        Lives here rather than in the loader because loading is not the only place a
        capability fails. Whatever reports a failure — the loader, the MCP server, anything
        later — has to scrub the same values, and the message that goes wrong is never the
        one somebody was careful with. It is `raise ValueError(f'the service rejected
        {token}')`, written in a hurry, on its way to /health.
        """
        schema = self.declaration.get('config') or {}
        for name, spec in schema.items():
            if spec.get('secret') and (value := self.config.get(name)):
                text = text.replace(str(value), REDACTED)
        return text


@dataclass
class Capability:
    """One implementation Harry found, and what became of it.

    `status` is `loaded` or `skipped` and nothing else. A capability replaced by one of
    the same name in a later root is skipped with `shadowed_by` set — it did not fail,
    it was taken over, and those read differently to whoever is wondering why their
    change had no effect.
    """

    name: str
    kind: str
    folder: Path
    root: Path
    status: str = LOADED
    reason: str = ''
    shadowed_by: Path | None = None
    target: Any | None = None
    """Whatever the capability registered, or None when it is a declaration alone."""
    context: Context | None = None
    """What the capability was handed, kept rather than dropped.

    Everything downstream needs the declaration and the body: a tool's body is the
    description Claude reads, its frontmatter carries the annotations, and a job's body is
    the brief. Re-reading the files later would be a second reader of the same format, and
    two readers of one format drift.

    None on a capability that was skipped before its declaration could be read.
    """

    @property
    def key(self) -> tuple[str, str]:
        """Kind and name together. Shadowing is per kind: a tool and a connector may
        share a name without one replacing the other."""
        return (self.kind, self.name)

    def as_health(self) -> dict[str, Any]:
        """One row of `/health`. Names only what the declaration already made public."""
        row: dict[str, Any] = {
            'name': self.name,
            'kind': self.kind,
            'status': self.status,
            'root': str(self.root),
        }
        if self.reason:
            row['reason'] = self.reason
        if self.shadowed_by is not None:
            row['shadowed_by'] = str(self.shadowed_by)
        return row


class Registry:
    """The `registry` one capability's `register()` is handed.

    None of these take a name. The name, the description, the annotations and
    `always_load` are all in the declaration the loader has already read, and passing
    them again would be a second copy that drifts from the first. **The declaration is
    the metadata; the Python is the behaviour.**

    Each returns what it was given, so it reads as a decorator:

        @registry.tool
        def weather_forecast(day: str) -> dict: ...
    """

    def __init__(self, capability: Capability) -> None:
        self._capability = capability

    def connector(self, target: Any) -> Any:
        """The client this connector reaches its service with."""
        return self._bind('connector', target)

    def tool(self, target: Any) -> Any:
        """The function behind this tool's one verb."""
        return self._bind('tool', target)

    def job(self, target: Any) -> Any:
        """What this job runs. A `trigger: claude` job registers nothing and needs none."""
        return self._bind('job', target)

    def _bind(self, kind: str, target: Any) -> Any:
        if kind != self._capability.kind:
            raise ContractError(
                f'registered a {kind} from a {self._capability.kind} folder. A folder is '
                f'one implementation of one kind — which one is its declaration, not its code. '
                f'A connector chooses what to expose as a tool in `provides:`.'
            )
        if self._capability.target is not None:
            raise ContractError(
                f'registered twice. One folder is one implementation; a second {kind} needs a second folder.'
            )
        self._capability.target = target
        return target


class Catalogue:
    """Everything Harry found, in the order it found it.

    Serving this is what makes a skipped capability visible instead of silent, which is
    the whole reason skipping is safe — **Alerting**, and `/health` until the feature
    that sends it to Slack lands.
    """

    def __init__(self, roots: Sequence[Path] = ()) -> None:
        self._found: list[Capability] = []
        self.roots = tuple(roots)
        """Where it looked. A capability missing from the list entirely is usually in a
        root nobody searched, and that is otherwise a silent, baffling failure."""

    def __iter__(self) -> Iterator[Capability]:
        return iter(self._found)

    def __len__(self) -> int:
        return len(self._found)

    def add(self, capability: Capability) -> Capability:
        self._found.append(capability)
        return capability

    def skip(self, capability: Capability, reason: str) -> Capability:
        """Record why this one is not running. The reason is the whole value here."""
        return self.add(self.withdraw(capability, reason))

    def withdraw(self, capability: Capability, reason: str) -> Capability:
        """One that loaded and then could not be used after all.

        Publishing happens after loading, so a tool whose annotations do not validate loads
        cleanly and fails when the MCP server reaches it. It is already in the catalogue,
        so this changes what it says rather than recording it a second time — and it has to
        cost exactly that capability, like every other failure here.
        """
        capability.status = SKIPPED
        capability.reason = capability.context.redact(reason) if capability.context is not None else reason
        return capability

    @property
    def loaded(self) -> list[Capability]:
        return [c for c in self._found if c.status == LOADED]

    @property
    def skipped(self) -> list[Capability]:
        return [c for c in self._found if c.status == SKIPPED]

    def get(self, kind: str, name: str) -> Capability | None:
        """The capability in effect under this name.

        A shadowed one shares its kind and name with the capability that replaced it, and
        it is a record of what was displaced rather than something anything should reach.
        So a loaded match wins, and `requires:` resolves against the version that is
        actually running.
        """
        matches = [c for c in self._found if c.key == (kind, name)]
        for capability in matches:
            if capability.status == LOADED:
                return capability
        return matches[-1] if matches else None

    def as_health(self) -> dict[str, Any]:
        """What `/health` answers with.

        Running with four of five capabilities is running. The count is here so the
        difference between "nothing installed" and "four things skipped" is one glance.
        """
        return {
            'status': 'ok',
            'roots': [str(root) for root in self.roots],
            'loaded': len(self.loaded),
            'skipped': len(self.skipped),
            'capabilities': [c.as_health() for c in self._found],
        }
