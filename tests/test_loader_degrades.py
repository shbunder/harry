"""One broken capability costs exactly itself.

The property the whole design rests on. A half-written folder is the normal state of
something somebody is working on, and it is the only state a third party's capability
ships in before it works — so every one of these is made to happen with a fixture that
really is broken, never with a mock. A degradation path asserted any other way is exactly
the control that cannot fail.
"""

from __future__ import annotations

import logging
from pathlib import Path

from harry.loader import load

from .test_loader import FIXTURES, reasons, root_with

EVERYTHING = (
    'connectors/weather',
    'connectors/broken',
    'connectors/unparseable',
    'connectors/icloud',
    'connectors/nosy',
    'connectors/noregister',
    'connectors/orphan',
    'connectors/mismatched',
    'connectors/disabled',
    'connectors/layered',
    'connectors/introspect',
    'connectors/wrongkind',
    'connectors/halfwritten',
    'tools/weather_forecast',
    'tools/icloud_list_events',
    'jobs/refresh',
    'jobs/morning-page',
)


def test_a_capability_that_raises_at_import_is_skipped_and_the_rest_come_up(tmp_path):
    root = root_with(tmp_path / 'root', 'connectors/broken', 'connectors/weather', 'jobs/refresh')

    catalogue = load([root])

    assert sorted(c.name for c in catalogue.loaded) == ['refresh', 'weather']
    assert [c.name for c in catalogue.skipped] == ['broken']


def test_the_failure_is_recorded_with_its_type_and_message(tmp_path):
    """ "This capability is broken" sends somebody looking. The exception type and the
    message it came with is already the answer."""
    catalogue = load([root_with(tmp_path / 'root', 'connectors/broken')])

    assert reasons(catalogue)['broken'] == ("ModuleNotFoundError: No module named 'a_dependency_nobody_installed'")


def test_a_capability_that_raises_while_registering_is_skipped_too(tmp_path):
    """Import is not the only moment a capability can fail. A client that dials out, a
    config value that is the wrong shape — all of it happens inside `register`."""
    root = root_with(tmp_path / 'root', 'connectors/weather')
    (root / 'connectors' / 'weather' / 'connector.py').write_text(
        'from harry.sdk import Context, Registry\n\n\n'
        'def register(registry: Registry, context: Context) -> None:\n'
        "    raise RuntimeError('the forecast service is down')\n",
        encoding='utf-8',
    )

    catalogue = load([root])

    assert catalogue.loaded == []
    assert reasons(catalogue)['weather'] == 'RuntimeError: the forecast service is down'


def test_one_broken_capability_among_many_costs_exactly_itself(tmp_path):
    """Eleven ways to be broken in one tree, and the six that work still work. This is the
    claim the design is built on, so it is asserted against every failure at once rather
    than one at a time in isolation."""
    catalogue = load([root_with(tmp_path / 'root', *EVERYTHING)])

    assert sorted(c.name for c in catalogue.loaded) == [
        'introspect',
        'layered',
        'morning-page',
        'refresh',
        'weather',
        'weather_forecast',
    ]
    assert sorted(c.name for c in catalogue.skipped) == [
        'broken',
        'disabled',
        'halfwritten',
        'icloud',
        'icloud_list_events',
        'mismatched',
        'noregister',
        'nosy',
        'orphan',
        'unparseable',
        'wrongkind',
    ]
    assert all(capability.reason for capability in catalogue.skipped), 'a skip with no reason is a silent one'


def test_every_skip_is_said_out_loud(tmp_path, caplog):
    """A skipped capability that reaches nobody looks exactly like one that was never
    installed. `/health` carries it; this is the half somebody watching a restart sees."""
    with caplog.at_level(logging.WARNING, logger='harry.loader'):
        load([root_with(tmp_path / 'root', 'connectors/broken', 'connectors/weather')])

    assert 'connector broken skipped: ModuleNotFoundError' in caplog.text
    assert 'weather' not in caplog.text


# ---------------------------------------------------------------------------
# Configuration that is not there
# ---------------------------------------------------------------------------


def test_a_missing_required_setting_disables_one_capability_not_harry(tmp_path, monkeypatch):
    """It does not crash, and — the part that matters — it does not pretend to work and
    fail at 06:30 with a stack trace from inside a client library."""
    monkeypatch.delenv('HARRY_ICLOUD_APP_PASSWORD', raising=False)
    root = root_with(tmp_path / 'root', 'connectors/icloud', 'connectors/weather')

    catalogue = load([root])

    icloud = catalogue.get('connector', 'icloud')
    assert icloud is not None and icloud.status == 'skipped'
    assert f'{icloud.name}: {icloud.reason}' == 'icloud: required setting app_password is not set'
    assert [c.name for c in catalogue.loaded] == ['weather']


def test_a_capability_with_its_setting_supplied_loads(tmp_path, monkeypatch):
    """The other side of the same gate. Without this, "skipped" could mean the check
    never passes for anybody."""
    monkeypatch.delenv('HARRY_ICLOUD_APP_PASSWORD', raising=False)
    root = root_with(tmp_path / 'root', 'connectors/icloud')
    (root / 'connectors' / 'icloud' / '.env.local').write_text('APP_PASSWORD=abcd-efgh-ijkl-mnop\n', encoding='utf-8')

    catalogue = load([root])

    assert [c.name for c in catalogue.loaded] == ['icloud']


def test_a_tool_whose_connector_did_not_load_does_not_load_either(tmp_path, monkeypatch):
    """It would otherwise register, look healthy, and fail on its first call — the same
    outcome arriving later and somewhere less obvious."""
    monkeypatch.delenv('HARRY_ICLOUD_APP_PASSWORD', raising=False)
    root = root_with(tmp_path / 'root', 'connectors/icloud', 'tools/icloud_list_events')

    catalogue = load([root])

    assert catalogue.loaded == []
    assert reasons(catalogue)['icloud_list_events'] == 'needs icloud, which did not load'


def test_a_tool_whose_connector_is_simply_absent_is_told_the_same_thing(tmp_path):
    """A connector that was never installed and one that failed are the same problem from
    the tool's side, and the message has to work for both."""
    catalogue = load([root_with(tmp_path / 'root', 'tools/icloud_list_events')])

    assert reasons(catalogue)['icloud_list_events'] == 'needs icloud, which did not load'


# ---------------------------------------------------------------------------
# A capability that reached past the SDK
# ---------------------------------------------------------------------------


def test_reaching_past_the_sdk_is_refused_before_the_module_runs(tmp_path):
    """The rule is what keeps core replaceable, so it is enforced at start-up rather than
    only in a review that catches it if somebody is looking.

    The fixture writes a marker file before its forbidden import. If that file appears,
    the check ran too late to matter."""
    root = root_with(tmp_path / 'root', 'connectors/nosy', 'connectors/weather')

    catalogue = load([root])

    assert [c.name for c in catalogue.loaded] == ['weather']
    assert 'harry.scheduler' in reasons(catalogue)['nosy']
    assert 'connector.py' in reasons(catalogue)['nosy']
    assert not (root / 'connectors' / 'nosy' / 'IT-RAN').exists(), 'the module ran before the check'


# ---------------------------------------------------------------------------
# Nothing that goes wrong may take a credential with it
# ---------------------------------------------------------------------------


def test_a_secret_in_an_exception_message_never_reaches_the_reason(tmp_path, monkeypatch):
    """Nobody writes a careful exception message when something has just gone wrong. The
    fixture raises `ValueError(f'the service rejected {api_key}')`, which is what people
    actually do — and that string is on its way to /health."""
    monkeypatch.delenv('HARRY_LEAKY_API_KEY', raising=False)
    root = root_with(tmp_path / 'root', 'connectors/leaky')
    secret = 'sk-live-9f3c7a21-do-not-log-me'
    (root / 'connectors' / 'leaky' / '.env.local').write_text(f'API_KEY={secret}\n', encoding='utf-8')

    catalogue = load([root])

    leaky = catalogue.get('connector', 'leaky')
    assert leaky is not None and leaky.status == 'skipped'
    assert secret not in leaky.reason
    assert leaky.reason == 'ValueError: the service rejected [redacted]'


def test_the_redaction_is_the_reason_the_secret_is_absent(tmp_path, monkeypatch, caplog):
    """Delete the redaction and this goes red. Without it the same run puts the credential
    in the log as well, which is the copy that gets shipped off the machine."""
    monkeypatch.delenv('HARRY_LEAKY_API_KEY', raising=False)
    root = root_with(tmp_path / 'root', 'connectors/leaky')
    secret = 'sk-live-9f3c7a21-do-not-log-me'
    (root / 'connectors' / 'leaky' / '.env.local').write_text(f'API_KEY={secret}\n', encoding='utf-8')

    with caplog.at_level(logging.WARNING, logger='harry.loader'):
        catalogue = load([root])

    assert secret not in caplog.text
    assert '[redacted]' in caplog.text
    assert secret not in str(catalogue.as_health())


def test_a_capability_with_no_secrets_keeps_its_message_intact(tmp_path):
    """Redaction replaces declared secrets and nothing else. A reason scrubbed into
    uselessness is its own failure."""
    root = root_with(tmp_path / 'root', 'connectors/broken')

    catalogue = load([root])

    assert '[redacted]' not in reasons(catalogue)['broken']


def test_the_declaration_is_never_copied_into_health(tmp_path, monkeypatch):
    """A capability's settings are not in the response at all, not even the ones that are
    not secret. /health says what loaded and why not — it is not a configuration dump."""
    monkeypatch.delenv('HARRY_LEAKY_API_KEY', raising=False)
    root = root_with(tmp_path / 'root', 'connectors/leaky', 'connectors/weather')
    (root / 'connectors' / 'leaky' / '.env.local').write_text('API_KEY=sk-live-abc\n', encoding='utf-8')

    health = str(load([root]).as_health())

    assert 'sk-live-abc' not in health
    assert 'Leuven' not in health


# ---------------------------------------------------------------------------
# The fixtures themselves
# ---------------------------------------------------------------------------


def test_every_fixture_capability_is_used_by_a_test():
    """A fixture nothing loads is a folder somebody will maintain for no reason. The
    broken ones are the point, so the roster that names them has to be exercised."""
    on_disk = {f'{kind.name}/{path.name}' for kind in FIXTURES.iterdir() if kind.is_dir() for path in kind.iterdir()}
    tests = Path(__file__).read_text(encoding='utf-8') + (Path(__file__).parent / 'test_loader.py').read_text(
        encoding='utf-8'
    )

    unused = sorted(name for name in on_disk if name not in tests)
    assert unused == [], f'fixtures no test loads: {unused}'


def test_registering_the_wrong_kind_costs_only_that_capability(tmp_path):
    """The registry refuses it; the loader has to turn that refusal into a skip with a
    readable reason rather than a traceback. Reached through load(), which is the only
    way production ever reaches those guards."""
    root = root_with(tmp_path / 'root', 'connectors/wrongkind', 'connectors/weather')

    catalogue = load([root])

    assert [c.name for c in catalogue.loaded] == ['weather']
    reason = reasons(catalogue)['wrongkind']
    assert reason.startswith('ContractError: registered a tool from a connector folder')
    assert 'provides:' in reason
