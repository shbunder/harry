"""Saying out loud that something went wrong.

The alerting path is the worst case for a test that cannot fail: an alert that does not
fire is discovered by the absence of something nobody was expecting. So every test here
makes a real fault happen and asserts that somebody was told — or, where that is the
point, that they were deliberately not told twice.
"""

from __future__ import annotations

import datetime as dt
import logging

import pytest

from harry.alerts import QUIET_FOR, Alerts, report_start_up
from harry.loader import load
from harry.registry import Capability, Catalogue, ContractError, Registry

from .test_loader import root_with


class Clock:
    """A hand-wound clock, so 24 hours costs nothing to wait for."""

    def __init__(self) -> None:
        self.at = dt.datetime(2026, 9, 13, 6, 30, tzinfo=dt.UTC)

    def __call__(self) -> dt.datetime:
        return self.at

    def forward(self, **by: float) -> None:
        self.at += dt.timedelta(**by)


class Somewhere:
    """A sink that remembers, and can be told to start failing."""

    def __init__(self) -> None:
        self.heard: list[str] = []
        self.broken = False

    def __call__(self, message: str) -> None:
        if self.broken:
            raise RuntimeError('the workspace is unreachable')
        self.heard.append(message)


# ---------------------------------------------------------------------------
# The seam: core reports, a capability carries
# ---------------------------------------------------------------------------


def test_an_alert_reaches_every_capability_that_offered_to_carry_one():
    first, second = Somewhere(), Somewhere()
    alerts = Alerts([first, second])

    assert alerts.send('the tablet push failed twice') is True
    assert first.heard == second.heard == ['the tablet push failed twice']


def test_the_message_is_what_the_caller_wrote_with_nothing_added():
    """No severity, no prefix, no formatting. Whoever raised the alert knows what happened;
    Harry deciding how to phrase it would be judgement."""
    sink = Somewhere()
    Alerts([sink]).send('De Tijd login needs refreshing')

    assert sink.heard == ['De Tijd login needs refreshing']


def test_nothing_registered_is_a_working_harry(caplog):
    """A fresh checkout has no Slack credential. Alerting that fell over without one would
    make the unconfigured case the broken case, which is backwards."""
    alerts = Alerts()

    with caplog.at_level(logging.WARNING, logger='harry.alerts'):
        assert alerts.send('nobody is listening yet') is True

    assert 'nobody is listening yet' in caplog.text


def test_sinks_come_from_the_catalogue_and_core_names_none_of_them(tmp_path):
    """Built from what loaded, so core holds a list of functions and knows nothing about
    any of them."""
    catalogue = Catalogue()
    carried: list[str] = []
    with_sink = Capability(name='somewhere', kind='connector', folder=tmp_path, root=tmp_path)
    Registry(with_sink).alerts(carried.append)
    catalogue.add(with_sink)
    catalogue.add(Capability(name='plain', kind='connector', folder=tmp_path, root=tmp_path))
    catalogue.skip(Capability(name='broken', kind='connector', folder=tmp_path, root=tmp_path), 'nope')

    Alerts.from_catalogue(catalogue).send('something happened')

    assert carried == ['something happened']


def test_a_sink_is_a_role_and_does_not_use_up_the_folders_one_implementation(tmp_path):
    """The Slack connector has to hand over both a client and a sink. `connector()` says
    what the folder is; `alerts()` says what it can also do."""
    capability = Capability(name='slack', kind='connector', folder=tmp_path, root=tmp_path)
    registry = Registry(capability)

    client = object()
    registry.connector(client)
    registry.alerts(lambda message: None)

    assert capability.target is client
    assert capability.alert_sink is not None


def test_a_second_sink_from_one_folder_is_refused(tmp_path):
    capability = Capability(name='slack', kind='connector', folder=tmp_path, root=tmp_path)
    registry = Registry(capability)
    registry.alerts(lambda message: None)

    with pytest.raises(ContractError, match='second alert sink'):
        registry.alerts(lambda message: None)


# ---------------------------------------------------------------------------
# A sink that fails
# ---------------------------------------------------------------------------


def test_a_sink_that_raises_does_not_reach_the_caller(caplog):
    """An alert path that raises takes down whatever was trying to report a problem, which
    is the worst direction for this particular code to fail in."""
    broken = Somewhere()
    broken.broken = True
    alerts = Alerts([broken])

    with caplog.at_level(logging.WARNING, logger='harry.alerts'):
        assert alerts.send('the feed is down') is False

    assert 'the workspace is unreachable' in caplog.text
    assert 'nobody was told: the feed is down' in caplog.text


def test_one_sink_failing_does_not_stop_another(caplog):
    broken, working = Somewhere(), Somewhere()
    broken.broken = True

    with caplog.at_level(logging.WARNING, logger='harry.alerts'):
        assert Alerts([broken, working]).send('the push failed') is True

    assert working.heard == ['the push failed']


def test_the_next_alert_is_still_attempted_after_a_failure():
    sink = Somewhere()
    sink.broken = True
    alerts = Alerts([sink])
    alerts.send('first')

    sink.broken = False
    assert alerts.send('second') is True
    assert sink.heard == ['second']


# ---------------------------------------------------------------------------
# The same fault, twice
# ---------------------------------------------------------------------------


def test_a_keyed_fault_is_said_once_a_day():
    clock = Clock()
    sink = Somewhere()
    alerts = Alerts([sink], now=clock)

    assert alerts.send('icloud is not configured', key='capability:connector:icloud') is True
    clock.forward(hours=4)
    assert alerts.send('icloud is not configured', key='capability:connector:icloud') is False
    clock.forward(hours=20, seconds=1)
    assert alerts.send('icloud is not configured', key='capability:connector:icloud') is True

    assert len(sink.heard) == 2


def test_an_alert_with_no_key_is_always_said():
    """A caller that did not name the fault cannot have meant "this is the same one"."""
    clock = Clock()
    sink = Somewhere()
    alerts = Alerts([sink], now=clock)

    for _ in range(3):
        assert alerts.send('the push failed') is True

    assert len(sink.heard) == 3


def test_two_different_faults_do_not_silence_each_other():
    sink = Somewhere()
    alerts = Alerts([sink], now=Clock())

    alerts.send('icloud is not configured', key='capability:connector:icloud')
    alerts.send('the tablet push failed', key='push:remarkable')

    assert len(sink.heard) == 2


def test_a_fault_nobody_heard_is_not_remembered():
    """The one that matters. If Slack was down, nothing was reported — recording the key
    anyway would suppress the retry for a day and the fault would never be heard at all."""
    clock = Clock()
    sink = Somewhere()
    sink.broken = True
    alerts = Alerts([sink], now=clock)

    assert alerts.send('icloud is not configured', key='capability:connector:icloud') is False

    sink.broken = False
    clock.forward(minutes=5)
    assert alerts.send('icloud is not configured', key='capability:connector:icloud') is True
    assert sink.heard == ['icloud is not configured']


def test_the_quiet_period_is_a_day():
    assert QUIET_FOR == dt.timedelta(hours=24)


# ---------------------------------------------------------------------------
# The first real caller: what did not come up
# ---------------------------------------------------------------------------


def test_a_capability_that_did_not_load_reaches_a_person(tmp_path, monkeypatch):
    """The case three features handed forward. /health carries it and nothing watches
    /health."""
    monkeypatch.delenv('HARRY_ICLOUD_APP_PASSWORD', raising=False)
    catalogue = load([root_with(tmp_path / 'root', 'connectors/icloud', 'connectors/weather')])
    sink = Somewhere()

    report_start_up(catalogue, Alerts([sink]))

    assert sink.heard == ['Harry started without the icloud connector: required setting app_password is not set']


def test_a_capability_that_loaded_produces_no_alert(tmp_path):
    catalogue = load([root_with(tmp_path / 'root', 'connectors/weather')])
    sink = Somewhere()

    report_start_up(catalogue, Alerts([sink]))

    assert sink.heard == []


def test_a_restart_loop_does_not_repeat_the_same_capability_within_the_day(tmp_path, monkeypatch):
    """Keyed on the capability, so a machine restarting every ten minutes does not send the
    same line every ten minutes."""
    monkeypatch.delenv('HARRY_ICLOUD_APP_PASSWORD', raising=False)
    root = root_with(tmp_path / 'root', 'connectors/icloud')
    clock = Clock()
    sink = Somewhere()
    alerts = Alerts([sink], now=clock)

    for _ in range(3):
        report_start_up(load([root]), alerts)
        clock.forward(minutes=10)

    assert len(sink.heard) == 1


def test_a_capability_that_was_replaced_is_not_reported_as_a_fault(tmp_path):
    """It did not fail — somebody put a newer one beside it on purpose. Reporting the swap
    mechanism as a fault would alert every morning."""
    bundled = root_with(tmp_path / 'bundled', 'connectors/weather')
    instance = root_with(tmp_path / 'instance', 'connectors/weather')
    catalogue = load([bundled, instance])
    sink = Somewhere()

    report_start_up(catalogue, Alerts([sink]))

    assert [c.name for c in catalogue.skipped] == ['weather'], 'the shadowed one should be recorded'
    assert sink.heard == []


def test_a_secret_in_the_reason_is_not_in_the_alert(tmp_path, monkeypatch):
    """A different path from protecting Harry's own token: this is somebody else's
    credential, quoted by the connector that failed with it in the message."""
    monkeypatch.delenv('HARRY_LEAKY_API_KEY', raising=False)
    root = root_with(tmp_path / 'root', 'connectors/leaky')
    secret = 'xoxb-not-mine-do-not-repeat-this'
    (root / 'connectors' / 'leaky' / '.env.local').write_text(f'API_KEY={secret}\n', encoding='utf-8')

    sink = Somewhere()
    report_start_up(load([root]), Alerts([sink]))

    assert sink.heard, 'the skipped capability should have been reported'
    assert secret not in sink.heard[0]
    assert '[redacted]' in sink.heard[0]
