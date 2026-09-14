"""The surface a capability is written against, and the rule that it reached no further.

Everything under `.harry/` — including folders written by people who have never read this
repository — depends on these three names and nothing else. So this file tests two things:
that the surface is exactly what it claims, and that a capability reaching past it is
caught before its code runs.
"""

from __future__ import annotations

import ast
import logging
from pathlib import Path

import pytest

from harry import sdk
from harry.boundary import forbidden_imports
from harry.config import OWNER, Principal
from harry.registry import Capability, Catalogue, Context, ContractError, Registry

SOURCE = Path(sdk.__file__).parent


def write(folder: Path, name: str, source: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_text(source, encoding='utf-8')
    return path


# ---------------------------------------------------------------------------
# What the SDK exposes, and what it reaches
# ---------------------------------------------------------------------------


def test_the_sdk_exposes_three_names_and_nothing_else():
    """A capability's whole vocabulary. Adding a fourth is a deliberate change to a
    contract every folder on disk is written against, so it should be hard to do by
    accident — which means something has to notice."""
    assert sdk.__all__ == ['Context', 'Principal', 'Registry']

    public = {name for name in vars(sdk) if not name.startswith('_')}
    assert public == set(sdk.__all__), f'harry.sdk also exposes {sorted(public - set(sdk.__all__))}'


def test_the_sdk_cannot_reach_the_loader_or_the_app():
    """In either direction. An SDK that imports a capability is a core that knows a
    capability's name; an SDK that imports the loader is a loader nothing can replace.

    Walks the import graph rather than one file, because `harry.registry` importing
    `harry.loader` would break this just as thoroughly as `harry.sdk` doing it."""

    def harry_imports(module: str) -> set[str]:
        path = SOURCE / f'{module.removeprefix("harry.")}.py'
        tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        found: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                found |= {a.name for a in node.names if a.name.startswith('harry')}
            elif isinstance(node, ast.ImportFrom) and (node.module or '').startswith('harry'):
                found.add(node.module or '')
        return found

    reachable: set[str] = set()
    pending = ['harry.sdk']
    while pending:
        module = pending.pop()
        for imported in harry_imports(module) - reachable:
            reachable.add(imported)
            pending.append(imported)

    assert reachable == {'harry.config', 'harry.registry'}, f'harry.sdk now reaches {sorted(reachable)}'


# ---------------------------------------------------------------------------
# The run-time check: a capability that reached past the SDK
# ---------------------------------------------------------------------------


def test_a_capability_that_imports_only_the_sdk_is_clean(tmp_path):
    write(tmp_path, 'connector.py', 'from harry.sdk import Context, Registry\n\n\ndef register(r, c):\n    pass\n')
    assert forbidden_imports(tmp_path) == []


@pytest.mark.parametrize(
    'source',
    [
        'import harry.scheduler\n',
        'import harry.store\n',
        'from harry.mcp import server\n',
        'from harry import main\n',
        'import harry\n',
        'import harry.scheduler as clock\n',
    ],
)
def test_reaching_past_the_sdk_is_caught(tmp_path, source):
    """Six spellings of the same reach. The rule is about what the capability can touch,
    not about how the import was written, and `import harry` counts because the package
    is the door to everything behind it."""
    write(tmp_path, 'connector.py', source)
    assert forbidden_imports(tmp_path), f'{source!r} was allowed through'


def test_the_allowed_spellings_of_the_sdk_all_pass(tmp_path):
    write(tmp_path, 'connector.py', 'import harry.sdk\nfrom harry import sdk\nfrom harry.sdk import Registry\n')
    assert forbidden_imports(tmp_path) == []


def test_the_whole_folder_is_read_not_only_the_entry_module(tmp_path):
    """The reach is usually in the client beside the entry module, not in it. A check
    that reads `connector.py` alone is one you get past by adding a file."""
    write(tmp_path, 'connector.py', 'from harry.sdk import Registry\nfrom .client import fetch\n')
    write(tmp_path / 'internals', 'client.py', 'from harry.store import db\n\n\ndef fetch():\n    return db\n')

    findings = forbidden_imports(tmp_path)
    assert findings, 'the helper module was never read'
    assert 'internals/client.py' in findings[0]
    assert 'harry.store' in findings[0]


def test_a_finding_names_the_file_the_line_and_the_import(tmp_path):
    """The reason lands in `/health` and in the log. "This capability is broken" sends
    somebody looking; "client.py:2 imports harry.store" is already the answer."""
    write(tmp_path, 'connector.py', 'from harry.sdk import Registry\nimport harry.scheduler\n')
    assert forbidden_imports(tmp_path) == ['connector.py:2 imports harry.scheduler']


def test_relative_imports_inside_the_folder_are_fine(tmp_path):
    """A capability is a folder, so the code in it may be more than one file."""
    write(tmp_path, 'connector.py', 'from .client import fetch\nfrom . import shared\n')
    write(tmp_path, 'client.py', 'def fetch():\n    return 1\n')
    write(tmp_path, 'shared.py', 'VALUE = 1\n')
    assert forbidden_imports(tmp_path) == []


def test_importing_anything_that_is_not_harry_is_none_of_this_rule(tmp_path):
    """The rule is about core, not about dependencies. A connector reaching iCloud needs
    caldav, and that was never the question."""
    write(tmp_path, 'connector.py', 'import caldav\nimport httpx\nfrom pathlib import Path\n')
    assert forbidden_imports(tmp_path) == []


# ---------------------------------------------------------------------------
# The registry a capability is handed
# ---------------------------------------------------------------------------


def a_capability(kind: str = 'connector', name: str = 'icloud', folder: Path | None = None) -> Capability:
    where = folder or Path('/nowhere')
    return Capability(name=name, kind=kind, folder=where, root=where.parent)


def test_registering_binds_the_implementation_to_its_folder():
    capability = a_capability()
    registry = Registry(capability)

    def client():
        return 'connected'

    registry.connector(client)
    assert capability.target is client


def test_each_method_reads_as_a_decorator():
    """`@registry.tool` over the function is the shape a capability actually writes, so
    each method returns what it was given."""
    capability = a_capability(kind='tool', name='weather_forecast')
    registry = Registry(capability)

    @registry.tool
    def weather_forecast(day: str) -> dict:
        return {'day': day}

    assert capability.target is weather_forecast
    assert weather_forecast('today') == {'day': 'today'}


def test_registering_the_wrong_kind_for_the_folder_is_refused():
    """A folder is one implementation of one kind, and which one is its declaration's
    business rather than its code's. A connector exposes a tool through `provides:`."""
    capability = a_capability(kind='connector', name='icloud')
    with pytest.raises(ContractError) as raised:
        Registry(capability).tool(lambda: None)
    assert 'tool' in str(raised.value) and 'connector' in str(raised.value)


def test_registering_twice_is_refused():
    capability = a_capability(kind='job', name='refresh')
    registry = Registry(capability)
    registry.job(lambda: None)
    with pytest.raises(ContractError, match='twice'):
        registry.job(lambda: None)


def test_a_capability_may_register_nothing_at_all():
    """A `trigger: claude` job is one markdown file with no Python. Its declaration is
    the whole capability, and `target` staying None is what that looks like."""
    capability = a_capability(kind='job', name='morning-page')
    assert capability.target is None
    assert capability.status == 'loaded'


# ---------------------------------------------------------------------------
# The context a capability is handed
# ---------------------------------------------------------------------------


def a_context(folder: Path, declaration: dict | None = None, config: dict | None = None) -> Context:
    return Context(
        name='icloud',
        kind='connector',
        folder=folder,
        declaration=declaration or {},
        body='',
        config=config or {},
        log=logging.getLogger('harry.capability.icloud'),
    )


def test_the_context_carries_the_declaration_body_verbatim(tmp_path):
    """Harry serves the body and never reads it — parsing it would be reasoning, and
    Harry does not reason."""
    body = 'Pick the six that matter.\n\n- and a list Harry must not interpret'
    context = Context(
        name='morning-page',
        kind='job',
        folder=tmp_path,
        declaration={'trigger': 'claude'},
        body=body,
        config={},
        log=logging.getLogger('harry.capability.morning-page'),
    )
    assert context.body == body


def test_config_for_resolves_one_persons_own_settings(tmp_path, monkeypatch):
    """Registration has no principal because it is not a call. A call that knows whose
    calendar it is asks here, and their own file under the data volume wins key by key."""
    import harry.config

    monkeypatch.delenv('HARRY_ICLOUD_USERNAME', raising=False)
    made = harry.config.Settings(data_dir=tmp_path / 'data')
    monkeypatch.setattr(harry.config, 'get_settings', lambda: made)

    folder = tmp_path / 'icloud'
    folder.mkdir()
    (folder / '.env').write_text('USERNAME=the-owner@example.com\n', encoding='utf-8')

    renee = Principal(id='renee', name='Renée')
    hers = harry.config.user_data_dir(renee) / 'connectors'
    hers.mkdir(parents=True)
    (hers / 'icloud.env').write_text('USERNAME=renee@example.com\n', encoding='utf-8')

    context = a_context(folder, declaration={'config': {'username': {'description': 'the account'}}})

    assert context.config_for(renee)['username'] == 'renee@example.com'
    assert context.config_for(OWNER)['username'] == 'the-owner@example.com'


# ---------------------------------------------------------------------------
# The catalogue everything downstream reads
# ---------------------------------------------------------------------------


def test_the_catalogue_separates_what_loaded_from_what_did_not(tmp_path):
    catalogue = Catalogue(roots=[tmp_path])
    catalogue.add(a_capability(name='weather', folder=tmp_path / 'weather'))
    catalogue.skip(a_capability(name='icloud', folder=tmp_path / 'icloud'), 'required setting app_password is not set')

    assert [c.name for c in catalogue.loaded] == ['weather']
    assert [c.name for c in catalogue.skipped] == ['icloud']
    assert len(catalogue) == 2


def test_get_returns_the_capability_in_effect_whatever_order_it_was_recorded(tmp_path):
    """A shadowed capability shares its kind and name with the one that replaced it. `get`
    has to answer with the version that is running — `requires:` resolves through it, and
    a tool told its connector failed when the replacement loaded fine is a tool that never
    comes up.

    Recorded loaded-first here on purpose: the loader happens to record the shadow first
    today, so relying on order would make this correct by accident.
    """
    catalogue = Catalogue()
    catalogue.add(a_capability(name='icloud', folder=tmp_path / 'instance'))
    displaced = a_capability(name='icloud', folder=tmp_path / 'bundled')
    displaced.shadowed_by = tmp_path / 'instance'
    catalogue.skip(displaced, f'replaced by {tmp_path / "instance"}')

    found = catalogue.get('connector', 'icloud')
    assert found is not None
    assert found.folder == tmp_path / 'instance'
    assert found.status == 'loaded'


def test_a_tool_and_a_connector_may_share_a_name(tmp_path):
    """Shadowing is per kind. Two folders called `weather` under different kinds are two
    different things, and neither replaces the other."""
    catalogue = Catalogue()
    catalogue.add(a_capability(kind='connector', name='weather'))
    catalogue.add(a_capability(kind='tool', name='weather'))

    assert catalogue.get('connector', 'weather') is not None
    assert catalogue.get('tool', 'weather') is not None
    assert catalogue.get('job', 'weather') is None


def test_health_carries_every_capability_with_its_reason(tmp_path):
    catalogue = Catalogue(roots=[tmp_path])
    catalogue.add(a_capability(name='weather', folder=tmp_path / 'weather'))
    catalogue.skip(a_capability(name='icloud', folder=tmp_path / 'icloud'), 'required setting app_password is not set')

    health = catalogue.as_health()

    assert health['status'] == 'ok'
    assert (health['loaded'], health['skipped']) == (1, 1)
    assert health['roots'] == [str(tmp_path)]
    rows = {row['name']: row for row in health['capabilities']}
    assert rows['weather']['status'] == 'loaded'
    assert 'reason' not in rows['weather']
    assert rows['icloud']['reason'] == 'required setting app_password is not set'


def test_a_shadowed_capability_reads_differently_from_a_broken_one(tmp_path):
    """It did not fail — it was taken over. Somebody wondering why their edit had no
    effect needs those to look different at a glance."""
    catalogue = Catalogue()
    earlier = a_capability(name='icloud', folder=tmp_path / 'bundled' / 'icloud')
    earlier.shadowed_by = tmp_path / 'instance' / 'icloud'
    catalogue.skip(earlier, f'replaced by {earlier.shadowed_by}')

    row = catalogue.as_health()['capabilities'][0]
    assert row['status'] == 'skipped'
    assert row['shadowed_by'] == str(tmp_path / 'instance' / 'icloud')


def test_the_context_surface_is_pinned():
    """Context has grown three times — connectors, then alert, each with an ADR. Nothing
    held that line until now: the test above pins what `harry.sdk` exports and says nothing
    about what is on the objects it exports.

    A twelfth name should be deliberate. If you are here because this went red, that is the
    test working: add the name below and say why in the decision record."""
    fields = set(Context.__dataclass_fields__)
    methods = {name for name in vars(Context) if not name.startswith('_') and callable(vars(Context)[name])}
    public = fields | methods

    assert public == {
        'name',
        'kind',
        'folder',
        'declaration',
        'body',
        'config',
        'log',
        'alerts',
        'connectors',
        'config_for',
        'redact',
        'alert',
    }
