"""Capabilities are found, read and registered — and core learns none of their names.

Every fixture here is a real folder under `tests/fixtures/capabilities/`, copied into a
temporary root. They are not in `.harry/` because `make lint` validates everything there,
and a folder with unclosed frontmatter parked in the repository would fail the gate on
every run, forever. `tests/fixtures/capabilities/README.md` says the same thing next to
the fixtures themselves.
"""

from __future__ import annotations

import ast
import logging
import shutil
from pathlib import Path

import pytest

from harry.loader import load

FIXTURES = Path(__file__).parent / 'fixtures' / 'capabilities'
REPO = Path(__file__).parent.parent


def root_with(where: Path, *capabilities: str) -> Path:
    """A capability root holding exactly the fixtures a test is about.

    `capabilities` are paths inside the fixture tree: `connectors/weather`.
    """
    where.mkdir(parents=True, exist_ok=True)
    for capability in capabilities:
        destination = where / capability
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(FIXTURES / capability, destination)
    return where


def reasons(catalogue) -> dict[str, str]:
    return {capability.name: capability.reason for capability in catalogue.skipped}


# ---------------------------------------------------------------------------
# Three kinds load, and core names none of them
# ---------------------------------------------------------------------------


def test_a_connector_a_tool_and_a_job_all_load(tmp_path):
    root = root_with(tmp_path / 'root', 'connectors/weather', 'tools/weather_forecast', 'jobs/refresh')

    catalogue = load([root])

    assert sorted(c.name for c in catalogue.loaded) == ['refresh', 'weather', 'weather_forecast']
    assert catalogue.skipped == []


def test_what_each_kind_handed_over_is_what_gets_used(tmp_path):
    """Registration is not a tick in a list — the thing registered is the thing the MCP
    server and the scheduler will call, so the test calls it."""
    root = root_with(tmp_path / 'root', 'connectors/weather', 'tools/weather_forecast', 'jobs/refresh')

    catalogue = load([root])

    connector = catalogue.get('connector', 'weather')
    assert connector is not None and connector.target is not None
    assert connector.target.today() == {'place': 'Leuven', 'summary': 'grey, as ever'}

    tool = catalogue.get('tool', 'weather_forecast')
    assert tool is not None and tool.target is not None
    assert tool.target()['summary'] == 'grey, as ever'

    job = catalogue.get('job', 'refresh')
    assert job is not None and job.target is not None
    assert job.target() == 'refreshed'


def test_core_names_no_capability():
    """The property the whole design rests on: adding a capability is a folder, and the
    moment core knows one by name that stops being true.

    It compares whole names rather than searching for the text, and it skips docstrings.
    `if name == 'weather'` is the violation and is caught; the sentence "one broken
    connector is logged and skipped" is prose, and a substring search would fail on the
    word `broken` for a reason that has nothing to do with the rule.
    """
    capabilities = {path.name for kind in FIXTURES.iterdir() if kind.is_dir() for path in kind.iterdir()}
    assert capabilities, 'no fixture capabilities to check against'

    offences = [
        f'{source.relative_to(REPO)} names {named}'
        for source in sorted((REPO / 'src' / 'harry').rglob('*.py'))
        for named in sorted(_names_in_code(source) & capabilities)
    ]

    assert offences == []


def _names_in_code(path: Path) -> set[str]:
    """Every name the code itself uses: string literals, identifiers, attributes, imports.

    Docstrings are left out. A capability's name in prose cannot make core depend on it —
    only a literal, an identifier or an import can.
    """
    tree = ast.parse(path.read_text(encoding='utf-8'))
    prose = {
        id(node.body[0].value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
        and node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
    }

    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in prose:
            found.add(node.value)
        elif isinstance(node, ast.Name):
            found.add(node.id)
        elif isinstance(node, ast.Attribute):
            found.add(node.attr)
        elif isinstance(node, ast.Import):
            found |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            found.add(node.module or '')
            found |= {alias.name for alias in node.names}
    return found


def test_the_check_would_catch_core_naming_one(tmp_path):
    """Delete the check and which test goes red — asked of the check itself. A capability
    name in a docstring passes; the same name in a branch does not."""
    innocent = tmp_path / 'innocent.py'
    innocent.write_text(
        '"""An instance drops its own weather beside a bundled one."""\n\nVALUE = 1\n', encoding='utf-8'
    )
    guilty = tmp_path / 'guilty.py'
    guilty.write_text("def pick(name):\n    if name == 'weather':\n        return 1\n", encoding='utf-8')

    assert 'weather' not in _names_in_code(innocent)
    assert 'weather' in _names_in_code(guilty)


# ---------------------------------------------------------------------------
# Reading a declaration
# ---------------------------------------------------------------------------


def test_a_folder_with_no_declaration_is_skipped(tmp_path):
    """The failure the filesystem format adds: it looks present and does nothing, where
    an import would have raised."""
    root = root_with(tmp_path / 'root', 'connectors/orphan', 'connectors/weather')

    catalogue = load([root])

    assert [c.name for c in catalogue.loaded] == ['weather']
    assert reasons(catalogue)['orphan'] == 'no CONNECTOR.md, so nothing here is loaded'


def test_a_declaration_that_does_not_parse_is_skipped_not_raised(tmp_path):
    """`make lint` catches this before it ships. Run time still has to survive one,
    because a third party's folder never passed your gate."""
    root = root_with(tmp_path / 'root', 'connectors/unparseable', 'connectors/weather')

    catalogue = load([root])

    assert [c.name for c in catalogue.loaded] == ['weather']
    assert 'never closed' in reasons(catalogue)['unparseable']


def test_a_name_that_disagrees_with_its_folder_is_skipped(tmp_path):
    """Guessing which one is right is how the wrong connector answers."""
    catalogue = load([root_with(tmp_path / 'root', 'connectors/mismatched')])

    assert catalogue.loaded == []
    assert reasons(catalogue)['mismatched'] == (
        "its declaration is named 'something-else' but the folder is 'mismatched'"
    )


def test_a_disabled_capability_is_skipped_before_its_code_runs(tmp_path):
    """`enabled: false` is how you switch one off without deleting the folder, so nothing
    in it may run — including whatever its module does at import."""
    root = root_with(tmp_path / 'root', 'connectors/disabled')

    catalogue = load([root])

    assert catalogue.loaded == []
    assert reasons(catalogue)['disabled'] == 'disabled in its declaration'
    assert not (root / 'connectors' / 'disabled' / 'IT-RAN').exists(), 'the disabled module was imported'


def test_the_declaration_and_its_body_reach_the_capability_verbatim(tmp_path):
    """Harry serves the body and never reads it. What it hands over has to be the file,
    not a cleaned-up version of the file."""
    root = root_with(tmp_path / 'root', 'connectors/weather')

    module = root / 'connectors' / 'weather' / 'connector.py'
    module.write_text(
        'from harry.sdk import Context, Registry\n\n\n'
        'def register(registry: Registry, context: Context) -> None:\n'
        "    registry.connector({'body': context.body, 'expires': context.declaration['expires']})\n",
        encoding='utf-8',
    )

    catalogue = load([root])
    weather = catalogue.get('connector', 'weather')

    assert weather is not None and weather.target is not None
    seen = weather.target
    assert seen['expires'] == 'never'
    assert seen['body'].startswith('Not a real connector.')
    assert '---' not in seen['body']


def test_a_capability_with_no_python_is_a_whole_capability(tmp_path):
    """A `trigger: claude` job is one markdown file, because Claude runs the half of it
    that needs a mind."""
    catalogue = load([root_with(tmp_path / 'root', 'jobs/morning-page')])

    page = catalogue.get('job', 'morning-page')
    assert page is not None
    assert page.status == 'loaded'
    assert page.target is None


def test_python_with_no_register_is_skipped(tmp_path):
    """Otherwise the folder looks installed and hands over nothing, which is the same
    outcome as a typo and reads like success."""
    catalogue = load([root_with(tmp_path / 'root', 'connectors/noregister')])

    assert catalogue.loaded == []
    assert reasons(catalogue)['noregister'] == 'connector.py has no register(registry, context)'


def test_a_capability_may_keep_its_client_in_a_second_file(tmp_path):
    """A capability is a folder. If the entry module could not import a sibling, every
    connector would have to be one file."""
    catalogue = load([root_with(tmp_path / 'root', 'connectors/layered')])

    layered = catalogue.get('connector', 'layered')
    assert layered is not None, 'the relative import failed'
    assert layered.status == 'loaded'
    assert layered.target is not None
    assert layered.target.fetch() == 'from the sibling module'


# ---------------------------------------------------------------------------
# More than one root: later wins, loudly
# ---------------------------------------------------------------------------


def test_a_later_root_replaces_an_earlier_capability_of_the_same_name(tmp_path, caplog):
    """The swap mechanism, and the reason the roots are a list: an instance drops its own
    folder beside a bundled one and takes over, with no fork and no patch."""
    bundled = root_with(tmp_path / 'bundled', 'connectors/weather')
    instance = root_with(tmp_path / 'instance', 'connectors/weather')
    (instance / 'connectors' / 'weather' / 'connector.py').write_text(
        'from harry.sdk import Context, Registry\n\n\n'
        'def register(registry: Registry, context: Context) -> None:\n'
        "    registry.connector('the instance version')\n",
        encoding='utf-8',
    )

    with caplog.at_level(logging.WARNING, logger='harry.loader'):
        catalogue = load([bundled, instance])

    weather = catalogue.get('connector', 'weather')
    assert weather is not None
    assert weather.target == 'the instance version'
    assert weather.root == instance

    shadowed = [c for c in catalogue.skipped if c.shadowed_by is not None]
    assert len(shadowed) == 1
    assert shadowed[0].folder == bundled / 'connectors' / 'weather'
    assert shadowed[0].shadowed_by == instance / 'connectors' / 'weather'

    expected = (
        f'weather: replaced by {instance / "connectors" / "weather"}, shadowing {bundled / "connectors" / "weather"}'
    )
    assert expected in caplog.text


def test_the_shadowed_one_is_never_loaded(tmp_path):
    """Running code that is about to be discarded means its side effects happen and its
    failures get reported, for a version nobody is using."""
    bundled = root_with(tmp_path / 'bundled', 'connectors/broken')
    instance = root_with(tmp_path / 'instance', 'connectors/broken')
    (instance / 'connectors' / 'broken' / 'connector.py').write_text(
        'from harry.sdk import Context, Registry\n\n\n'
        'def register(registry: Registry, context: Context) -> None:\n'
        "    registry.connector('this one works')\n",
        encoding='utf-8',
    )

    catalogue = load([bundled, instance])

    broken = catalogue.get('connector', 'broken')
    assert broken is not None and broken.status == 'loaded'
    assert [c.reason for c in catalogue.skipped] == [f'replaced by {instance / "connectors" / "broken"}']


def test_a_tool_and_a_connector_of_the_same_name_do_not_shadow_each_other(tmp_path):
    """Shadowing is per kind. Two folders called `weather` under different kinds are two
    different things."""
    root = root_with(tmp_path / 'root', 'connectors/weather')
    shutil.copytree(FIXTURES / 'tools/weather_forecast', root / 'tools' / 'weather')
    declaration = root / 'tools' / 'weather' / 'TOOL.md'
    declaration.write_text(
        declaration.read_text(encoding='utf-8')
        .replace('name: weather_forecast', 'name: weather')
        .replace('requires: [weather]', 'requires: []'),
        encoding='utf-8',
    )

    catalogue = load([root])

    assert catalogue.get('connector', 'weather') is not None
    assert catalogue.get('tool', 'weather') is not None
    assert len(catalogue.loaded) == 2


def test_a_root_that_does_not_exist_is_not_an_error(tmp_path):
    """Bundled is empty today and `$HARRY_CAPABILITIES_DIR` is usually unset."""
    catalogue = load([tmp_path / 'nowhere', root_with(tmp_path / 'root', 'connectors/weather')])

    assert [c.name for c in catalogue.loaded] == ['weather']


def test_nothing_on_disk_is_a_valid_start(tmp_path, caplog):
    """A fresh install is not an error — but a Harry that found nothing and a Harry that
    failed to look are identical unless one of them says so."""
    with caplog.at_level(logging.INFO, logger='harry.loader'):
        catalogue = load([tmp_path / 'empty'])

    assert len(catalogue) == 0
    assert 'no capabilities found' in caplog.text


# ---------------------------------------------------------------------------
# Out of tree: a capability that is not in this repository at all
# ---------------------------------------------------------------------------


@pytest.fixture
def settings(monkeypatch):
    def build(**kwargs):
        import harry.config

        made = harry.config.Settings(**kwargs)
        monkeypatch.setattr(harry.config, 'get_settings', lambda: made)
        return made

    return build


def test_a_capability_outside_the_repository_loads_identically(tmp_path, settings, monkeypatch):
    """A contract that only works in-tree is not a contract. This goes through
    `capability_roots()` rather than passing a path, because that resolution is the part
    that would break."""
    import harry.config

    instance = tmp_path / 'instance'
    (instance / '.harry').mkdir(parents=True)
    elsewhere = root_with(tmp_path / 'elsewhere', 'connectors/weather')

    settings(capabilities_dir=elsewhere)
    monkeypatch.setattr(harry.config, 'BUNDLED_CAPABILITIES', tmp_path / 'no-bundled')
    monkeypatch.chdir(instance)

    catalogue = load()

    weather = catalogue.get('connector', 'weather')
    assert weather is not None and weather.status == 'loaded'
    assert weather.root == elsewhere.resolve()


def test_an_out_of_tree_capability_reads_its_settings_from_its_own_folder(tmp_path, settings, monkeypatch):
    """Not from the repository's. The folder is the namespace, wherever the folder is."""
    import harry.config

    monkeypatch.delenv('HARRY_WEATHER_PLACE', raising=False)
    instance = tmp_path / 'instance'
    (instance / '.harry').mkdir(parents=True)
    elsewhere = root_with(tmp_path / 'elsewhere', 'connectors/weather')
    (elsewhere / 'connectors' / 'weather' / '.env.local').write_text('PLACE=Ghent\n', encoding='utf-8')

    settings(capabilities_dir=elsewhere)
    monkeypatch.setattr(harry.config, 'BUNDLED_CAPABILITIES', tmp_path / 'no-bundled')
    monkeypatch.chdir(instance)

    weather = load().get('connector', 'weather')

    assert weather is not None and weather.target is not None
    assert weather.target.place == 'Ghent'
