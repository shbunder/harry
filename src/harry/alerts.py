"""Saying out loud that something went wrong.

Harry's whole design is degradation: a feed dies and the page renders, a credential lapses
and one source falls back, a capability is half-written and the rest come up. Every one of
those is invisible when it works, which means **every one is invisible when it does not.**
A morning page that lost De Tijd three weeks ago looks exactly like one that had no De Tijd
article that day.

So core has to be able to report a fault — without knowing where it goes. A capability
offers itself with `registry.alerts(fn)`; this holds whatever offered and calls them all.
Core names nothing, and a second somewhere for alerts to go is another folder.

**Zero sinks is a working Harry.** With nothing registered an alert is a WARNING in the log
and nothing else. A fresh checkout has no Slack credential, and alerting that fell over
without one would make the unconfigured case the broken case.
"""

from __future__ import annotations

import datetime as dt
import logging
from collections.abc import Callable, Iterable, Sequence

from harry.registry import Capability, Catalogue

LOG = logging.getLogger('harry.alerts')

Sink = Callable[[str], None]

QUIET_FOR = dt.timedelta(hours=24)
"""How long a keyed fault stays quiet after it has been reported."""


class Alerts:
    """Everywhere a fault can be said, and what has already been said today.

    Built after loading, because a sink is a capability and a capability has to load before
    it can carry news.
    """

    def __init__(self, sinks: Sequence[Sink] = (), *, now: Callable[[], dt.datetime] | None = None) -> None:
        self._sinks = list(sinks)
        self._now = now or (lambda: dt.datetime.now(dt.UTC))
        self._said: dict[str, dt.datetime] = {}

    @classmethod
    def from_catalogue(cls, catalogue: Catalogue, *, now: Callable[[], dt.datetime] | None = None) -> Alerts:
        sinks = [c.alert_sink for c in catalogue.loaded if c.alert_sink is not None]
        LOG.info('%d place(s) to send an alert', len(sinks))
        return cls(sinks, now=now)

    def send(self, message: str, *, key: str | None = None) -> bool:
        """Report one fault. True if it was said, False if it was held back.

        `key` is what makes a fault the same fault. One carrying a key is said at most once
        in 24 hours; one with no key is always said, because a caller that did not name the
        fault cannot have meant "this is the same one".
        """
        if key is not None and self._still_quiet(key):
            LOG.debug('already reported %s today: %s', key, message)
            return False

        delivered = self._deliver(message)
        if delivered and key is not None:
            self._forget_what_is_old()
            self._said[key] = self._now()
        return delivered

    def _forget_what_is_old(self) -> None:
        """Drop keys that are past their quiet period.

        Today every key is a capability, so the record is bounded by the number of folders
        on disk. `send()` is public, though, and a caller keying on an article id or a URL
        would grow it forever in a process that runs for months.
        """
        cutoff = self._now() - QUIET_FOR
        self._said = {key: at for key, at in self._said.items() if at > cutoff}

    def _still_quiet(self, key: str) -> bool:
        said = self._said.get(key)
        return said is not None and self._now() - said < QUIET_FOR

    def _deliver(self, message: str) -> bool:
        """Hand the message to every sink. True if any of them took it.

        **A sink that raises does not count**, and that is the whole reason this returns
        anything: a fault held back because Slack was down is a fault nobody ever hears
        about. Not recording it means the next occurrence tries again.

        With no sinks at all, the log line *is* the delivery. That is a configured Harry
        with nowhere to send, not a failed send.
        """
        if not self._sinks:
            LOG.warning('%s', message)
            return True

        delivered = False
        for sink in self._sinks:
            try:
                sink(message)
                delivered = True
            except Exception as error:  # noqa: BLE001 — an alert path that raises takes down
                # whatever was trying to report a problem, which is the worst direction for
                # this particular code to fail in.
                LOG.warning('could not send an alert: %s: %s', type(error).__name__, error)
        if not delivered:
            LOG.warning('nobody was told: %s', message)
        return delivered


def report_start_up(catalogue: Catalogue, alerts: Alerts) -> None:
    """Tell somebody which capabilities did not come up.

    The case three features handed forward. A capability skipped three weeks ago looks
    exactly like one that was never installed, and `/health` carries it while nothing
    watches `/health`.

    The reason is already scrubbed of that capability's own secrets — `Catalogue.skip`
    does it on the way in — so this cannot leak somebody else's credential by quoting the
    message it failed with.
    """
    for capability in _failed(catalogue):
        alerts.send(
            f'Harry started without the {capability.name} {capability.kind}: {capability.reason}',
            key=f'capability:{capability.kind}:{capability.name}',
        )


def _failed(catalogue: Catalogue) -> Iterable[Capability]:
    """Skipped, but not merely replaced.

    A capability shadowed by one of the same name in a later root did not fail — it was
    taken over, on purpose, by somebody who put it there. Reporting that as a fault would
    mean the swap mechanism alerts every morning.
    """
    return [c for c in catalogue.skipped if c.shadowed_by is None]
