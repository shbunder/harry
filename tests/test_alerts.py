# pyright: reportPrivateUsage=false
#
# One test reads `Alerts._said` directly. What forgetting old keys does is keep that
# record from growing without limit, and its size is the only thing that shows it —
# there is no behaviour to watch from outside. A public accessor existing only for this
# would be worse than the pragma.
"""Saying out loud that something went wrong.

The alerting path is the worst case for a test that cannot fail: an alert that does not
fire is discovered by the absence of something nobody was expecting. So every test here
makes a real fault happen and asserts that somebody was told — or, where that is the
point, that they were deliberately not told twice.
"""

from __future__ import annotations

import datetime as dt
import logging
from pathlib import Path

import pytest

from harry.alerts import QUIET_FOR, Alerts, report_start_up
from harry.loader import load
from harry.registry import Capability, Catalogue, Context, ContractError, Registry

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


def test_nothing_registered_is_a_working_harry(caplog, tmp_path):
    """A fresh checkout has no Slack credential. Alerting that fell over without one would
    make the unconfigured case the broken case, which is backwards.

    Attached with nothing, so the log line **is** the delivery — which is what makes a
    keyed fault log once a day rather than every five minutes."""
    alerts = Alerts()
    alerts.attach(Catalogue())

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


# ---------------------------------------------------------------------------
# The way production actually reaches all of this
# ---------------------------------------------------------------------------


def test_the_real_app_tells_a_sink_what_did_not_come_up(tmp_path, monkeypatch):
    """Through `build_app()`, which is the only thing that calls `report_start_up` in
    production. Every test above calls it directly, and a test one layer beneath the real
    caller cannot notice the real caller being removed.

    It also pins the ordering the story asks for: the sink is a capability, so a sink that
    had not loaded yet would hear nothing.
    """
    import harry.config
    from harry.main import build_app

    monkeypatch.delenv('HARRY_ICLOUD_APP_PASSWORD', raising=False)
    harry.config.get_settings.cache_clear()
    monkeypatch.setattr(harry.config, 'BUNDLED_CAPABILITIES', tmp_path / 'no-bundled')
    root_with(tmp_path / '.harry', 'connectors/listener', 'connectors/icloud', 'connectors/weather')
    monkeypatch.chdir(tmp_path)

    try:
        build_app()
    finally:
        harry.config.get_settings.cache_clear()

    heard = (tmp_path / '.harry' / 'connectors' / 'listener' / 'heard.txt').read_text(encoding='utf-8').splitlines()

    assert heard == ['Harry started without the icloud connector: required setting app_password is not set']


def test_forgetting_keeps_the_record_from_growing_without_limit():
    """`send()` is public. A caller keying on an article id in a process that runs for
    months is the case this is for, and the capability keys of today would never show it."""
    clock = Clock()
    alerts = Alerts([Somewhere()], now=clock)

    for day in range(5):
        alerts.send('something', key=f'article:{day}')
        clock.forward(hours=25)

    assert len(alerts._said) == 1


# ---------------------------------------------------------------------------
# A capability saying something went wrong
# ---------------------------------------------------------------------------


def a_context(alerts, *, name='icloud', kind='connector', declaration=None, config=None) -> Context:
    return Context(
        name=name,
        kind=kind,
        folder=Path('/nowhere'),
        declaration=declaration or {},
        body='',
        config=config or {},
        log=logging.getLogger(f'harry.capability.{name}'),
        alerts=alerts,
    )


def test_a_capability_can_say_that_something_went_wrong():
    """The half that was missing. A capability could offer somewhere alerts go and had no
    way to raise one — so the connector that knows its credential has lapsed could not
    say so, which is the exact thing alerting exists for."""
    sink = Somewhere()
    alerts = Alerts()
    alerts.attach(Catalogue())
    alerts._sinks = [sink]  # noqa: SLF001 — a catalogue here would be a fixture for one line

    assert a_context(alerts).alert('the app password has stopped working') is True
    assert sink.heard == ['the app password has stopped working']


def test_the_message_is_exactly_what_the_capability_wrote():
    sink = Somewhere()
    alerts = Alerts([sink])

    a_context(alerts).alert('De Tijd login needs refreshing')

    assert sink.heard == ['De Tijd login needs refreshing']


def test_two_capabilities_using_the_same_key_do_not_silence_each_other():
    """Core scopes the key, so a capability passes what is meaningful to it and never has
    to think about what anybody else might have picked."""
    sink = Somewhere()
    alerts = Alerts([sink], now=Clock())

    a_context(alerts, name='icloud').alert('icloud is down', key='down')
    a_context(alerts, name='news').alert('the feed is down', key='down')

    assert len(sink.heard) == 2


def test_one_capability_repeating_itself_still_reports_once_a_day():
    clock = Clock()
    sink = Somewhere()
    alerts = Alerts([sink], now=clock)
    context = a_context(alerts)

    assert context.alert('the feed is down', key='feed') is True
    clock.forward(hours=4)
    assert context.alert('the feed is down', key='feed') is False
    clock.forward(hours=20, seconds=1)
    assert context.alert('the feed is down', key='feed') is True


def test_a_declared_secret_is_scrubbed_before_any_sink_sees_it():
    """A log line stays on the machine. An alert goes to Slack, so this path needs the
    scrubbing more than the one it was built for."""
    sink = Somewhere()
    context = a_context(
        Alerts([sink]),
        declaration={'config': {'app_password': {'description': 'x', 'secret': True}}},
        config={'app_password': 'abcd-efgh-ijkl-mnop'},
    )

    context.alert('the service rejected abcd-efgh-ijkl-mnop')

    assert sink.heard == ['the service rejected [redacted]']


def test_alerting_never_breaks_the_capability(caplog):
    broken = Somewhere()
    broken.broken = True

    with caplog.at_level(logging.WARNING, logger='harry.alerts'):
        assert a_context(Alerts([broken])).alert('something happened') is False

    assert 'the workspace is unreachable' in caplog.text


def test_before_the_sinks_are_attached_the_key_is_not_recorded(caplog):
    """The bug this feature nearly shipped. Attached-with-nothing counts as delivery, so
    reusing it for not-attached-yet would record the key against nobody — and hold back the
    same fault when it happens for real at 06:30."""
    clock = Clock()
    alerts = Alerts(now=clock)
    context = a_context(alerts)

    with caplog.at_level(logging.WARNING, logger='harry.alerts'):
        assert context.alert('the session has expired', key='session') is False

    sink = Somewhere()
    alerts._sinks = [sink]  # noqa: SLF001 — standing in for attach() with one sink
    alerts._attached = True  # noqa: SLF001
    clock.forward(minutes=5)

    assert context.alert('the session has expired', key='session') is True
    assert sink.heard == ['the session has expired']


def test_a_sink_that_alerts_about_itself_is_refused_re_entry(caplog):
    """The Slack connector is a sink. Alerting from its own failure path would recurse:
    send, deliver, sink, alert, send. The key cannot stop it — the key is written only
    after delivery returns."""
    alerts = Alerts()
    heard: list[str] = []

    def a_sink_that_alerts(message: str) -> None:
        heard.append(message)
        a_context(alerts, name='slack').alert('I could not deliver that', key='undeliverable')

    alerts.attach(Catalogue())
    alerts._sinks = [a_sink_that_alerts]  # noqa: SLF001

    with caplog.at_level(logging.WARNING, logger='harry.alerts'):
        alerts.send('the tablet push failed')

    assert heard == ['the tablet push failed'], 'the inner alert should not have gone round again'
    assert 'dropped an alert raised while delivering one' in caplog.text


# ---------------------------------------------------------------------------
# Through the loader, the way production reaches it
# ---------------------------------------------------------------------------


def test_a_loaded_capability_alerts_through_the_one_it_was_handed(tmp_path, monkeypatch):
    """Every test above builds a Context by hand. This one goes through load(), which is
    the only thing that builds one in production."""
    monkeypatch.delenv('HARRY_COMPLAINER_TOKEN', raising=False)
    root = root_with(tmp_path / 'root', 'connectors/complainer')
    (root / 'connectors' / 'complainer' / '.env.local').write_text('TOKEN=sk-live-not-for-slack\n', encoding='utf-8')

    sink = Somewhere()
    alerts = Alerts()
    catalogue = load([root], alerts=alerts)
    alerts.attach(catalogue)
    alerts._sinks = [sink]  # noqa: SLF001 — the catalogue has no sink capability in it

    complainer = catalogue.get('connector', 'complainer')
    assert complainer is not None and complainer.target is not None
    assert complainer.target.give_up() is True

    assert sink.heard == ['the service rejected [redacted]'], 'the credential reached Slack'


def test_an_alert_raised_while_loading_is_logged_and_leaves_the_key_free(tmp_path, caplog):
    """The bug this feature nearly shipped, through the real path."""
    root = root_with(tmp_path / 'root', 'connectors/tattletale')
    alerts = Alerts()

    with caplog.at_level(logging.WARNING, logger='harry.alerts'):
        catalogue = load([root], alerts=alerts)
        alerts.attach(catalogue)

    assert 'I have nothing to say yet' in caplog.text
    tattletale = catalogue.get('connector', 'tattletale')
    assert tattletale is not None, 'it should still load'

    sink = Somewhere()
    alerts._sinks = [sink]  # noqa: SLF001
    context = tattletale.context
    assert context is not None
    assert context.alert('I have something to say now', key='too-early') is True
    assert sink.heard == ['I have something to say now']


def test_a_capability_reaching_for_harry_alerts_is_still_refused(tmp_path):
    """context.alert is the only way in. Reaching for the module directly would hand a
    capability every sink, which is core's business."""
    catalogue = load([root_with(tmp_path / 'root', 'connectors/eavesdropper')])

    eavesdropper = catalogue.get('connector', 'eavesdropper')
    assert eavesdropper is not None and eavesdropper.status == 'skipped'
    assert 'harry.alerts' in eavesdropper.reason


def test_the_no_sink_log_line_names_the_capability(caplog):
    """With nothing registered the log line *is* the delivery, and one that does not say
    which capability raised it is unusable the moment there are thirty of them and the
    message is "the feed is down"."""
    alerts = Alerts()
    alerts.attach(Catalogue())

    with caplog.at_level(logging.WARNING, logger='harry.alerts'):
        a_context(alerts, name='tijd').alert('the session has expired')

    assert 'connector tijd: the session has expired' in caplog.text


def test_a_context_with_no_alerts_at_all_logs_under_its_own_name(caplog):
    """What `load()` builds when nobody passes an Alerts, which is most of this suite. Its
    own logger already carries the capability's name."""
    with caplog.at_level(logging.WARNING, logger='harry.capability.tijd'):
        assert a_context(None, name='tijd').alert('the session has expired') is False

    assert 'the session has expired' in caplog.text


def test_the_constructor_and_the_flag_cannot_disagree():
    """`Alerts([])` is not attached — nothing has read a catalogue — so a keyed alert is not
    recorded against nobody. `Alerts([sink])` is."""
    assert Alerts([]).send('nowhere to go', key='k') is False
    assert Alerts([Somewhere()]).send('somewhere to go', key='k') is True


def test_an_alert_from_another_thread_is_not_dropped_while_a_sink_is_busy():
    """The guard is for a sink alerting about itself — re-entry on one thread. Process-wide
    it would also drop an unrelated alert raised while a sink was blocking, and the Slack
    sink blocks for up to five seconds while the scheduler runs beside it."""
    import threading
    import time

    heard: list[str] = []
    started = threading.Event()

    def slow(message: str) -> None:
        heard.append(message)
        started.set()
        time.sleep(0.4)

    alerts = Alerts([slow])
    first = threading.Thread(target=lambda: alerts.send('the tablet push failed twice'))
    first.start()
    assert started.wait(2), 'the slow sink never started'

    alerts.send('the De Tijd session has expired')
    first.join(2)

    assert sorted(heard) == ['the De Tijd session has expired', 'the tablet push failed twice']
