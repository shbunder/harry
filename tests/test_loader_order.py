"""A connector can name another connector, and is loaded after it.

Connectors used to load in folder-name order, full stop. A connector naming a later one
under `optional:` was then handed nothing, every start, and looked healthy doing it. These
tests go in through `load()`, the way Harry starts, and read what each connector was
handed and the order the registrations actually ran in — not what an ordering function
returns.
"""

from __future__ import annotations

import logging
from pathlib import Path

from harry.loader import load
from harry.registry import LOADED, SKIPPED

REGISTERS = '''\
from harry.sdk import Context, Registry


class Handed:
    """What this connector was given, so a test can read it back."""

    def __init__(self, name, connectors):
        self.name = name
        self.connectors = dict(connectors)


def register(registry: Registry, context: Context) -> None:
    # The folder two levels up is the capability root, which the test owns: appending here
    # records the order registrations really ran in.
    with open(context.folder.parent.parent / 'order.txt', 'a', encoding='utf-8') as order:
        order.write(context.name + '\\n')
    registry.connector(Handed(context.name, context.connectors))
'''


def connector(root: Path, name: str, lists: str = '', python: bool = True) -> None:
    folder = root / 'connectors' / name
    folder.mkdir(parents=True)
    (folder / 'CONNECTOR.md').write_text(
        f'---\nname: {name}\ndescription: {name}, for a test\nexpires: never\nenabled: true\n{lists}---\n\nBody.\n',
        encoding='utf-8',
    )
    if python:
        (folder / 'connector.py').write_text(REGISTERS, encoding='utf-8')


def order(root: Path) -> list[str]:
    path = root / 'order.txt'
    return path.read_text(encoding='utf-8').split() if path.exists() else []


def handed(catalogue, name: str) -> dict:
    found = catalogue.get('connector', name)
    assert found is not None and found.status == LOADED, found and found.reason
    return {key: value.name for key, value in found.target.connectors.items()}


# ---------------------------------------------------------------------------
# Naming a connector
# ---------------------------------------------------------------------------


def test_a_connector_naming_a_later_one_as_optional_loads_after_it_and_is_handed_it(tmp_path):
    connector(tmp_path, 'alpha', 'optional: [zeta]\n')
    connector(tmp_path, 'zeta')

    catalogue = load(roots=[tmp_path])

    assert order(tmp_path) == ['zeta', 'alpha']
    assert handed(catalogue, 'alpha') == {'zeta': 'zeta'}


def test_a_connector_requiring_a_later_one_loads_after_it(tmp_path):
    connector(tmp_path, 'alpha', 'requires: [zeta]\n')
    connector(tmp_path, 'zeta')

    catalogue = load(roots=[tmp_path])

    assert order(tmp_path) == ['zeta', 'alpha']
    assert handed(catalogue, 'alpha') == {'zeta': 'zeta'}


def test_a_connector_requiring_one_that_did_not_load_is_skipped_saying_so(tmp_path):
    connector(tmp_path, 'alpha', 'requires: [zeta]\n')
    connector(tmp_path, 'zeta', 'config:\n  token:\n    description: A token\n    required: true\n')

    catalogue = load(roots=[tmp_path])

    alpha = catalogue.get('connector', 'alpha')
    assert alpha is not None and alpha.status == SKIPPED
    assert alpha.reason == 'needs zeta, which did not load'


def test_connectors_naming_nothing_load_in_folder_order_as_before(tmp_path):
    for name in ('charlie', 'alpha', 'bravo'):
        connector(tmp_path, name)

    load(roots=[tmp_path])

    assert order(tmp_path) == ['alpha', 'bravo', 'charlie']


# ---------------------------------------------------------------------------
# Loops, which the lint refuses and a running Harry must survive
# ---------------------------------------------------------------------------


def test_two_connectors_naming_each_other_as_optional_both_load(tmp_path, caplog):
    connector(tmp_path, 'alpha', 'optional: [beta]\n')
    connector(tmp_path, 'beta', 'optional: [alpha]\n')

    with caplog.at_level(logging.WARNING, logger='harry.loader'):
        catalogue = load(roots=[tmp_path])

    assert order(tmp_path) == ['alpha', 'beta']
    assert handed(catalogue, 'alpha') == {}, 'alpha loaded first, so beta was not there to hand over'
    assert handed(catalogue, 'beta') == {'alpha': 'alpha'}
    assert any('alpha, beta name each other' in record.getMessage() for record in caplog.records)


def test_two_connectors_requiring_each_other_are_both_skipped_and_nothing_raises(tmp_path):
    connector(tmp_path, 'alpha', 'requires: [beta]\n')
    connector(tmp_path, 'beta', 'requires: [alpha]\n')

    catalogue = load(roots=[tmp_path])

    reasons = {c.name: c.reason for c in catalogue.skipped}
    assert reasons == {'alpha': 'needs beta, which did not load', 'beta': 'needs alpha, which did not load'}


def test_a_connector_naming_itself_loads_and_is_handed_nothing(tmp_path, caplog):
    connector(tmp_path, 'alpha', 'optional: [alpha]\n')

    with caplog.at_level(logging.WARNING, logger='harry.loader'):
        catalogue = load(roots=[tmp_path])

    assert handed(catalogue, 'alpha') == {}
    assert any('alpha name each other' in record.getMessage() for record in caplog.records)


def test_a_longer_loop_loads_its_members_in_folder_order(tmp_path):
    """a → b → c → a. Breaking it one member at a time would load a, c, b."""
    connector(tmp_path, 'alpha', 'optional: [bravo]\n')
    connector(tmp_path, 'bravo', 'optional: [charlie]\n')
    connector(tmp_path, 'charlie', 'optional: [alpha]\n')

    load(roots=[tmp_path])

    assert order(tmp_path) == ['alpha', 'bravo', 'charlie']


def test_a_loop_loads_after_what_it_names_outside_itself(tmp_path):
    connector(tmp_path, 'alpha', 'optional: [bravo, zulu]\n')
    connector(tmp_path, 'bravo', 'optional: [alpha]\n')
    connector(tmp_path, 'zulu')

    catalogue = load(roots=[tmp_path])

    assert order(tmp_path) == ['zulu', 'alpha', 'bravo']
    assert handed(catalogue, 'alpha') == {'zulu': 'zulu'}


def test_what_waits_on_a_loop_loads_after_the_whole_loop(tmp_path):
    connector(tmp_path, 'alpha', 'optional: [yankee]\n')
    connector(tmp_path, 'xray', 'optional: [yankee]\n')
    connector(tmp_path, 'yankee', 'optional: [xray]\n')

    catalogue = load(roots=[tmp_path])

    assert order(tmp_path) == ['xray', 'yankee', 'alpha']
    assert handed(catalogue, 'alpha') == {'yankee': 'yankee'}


# ---------------------------------------------------------------------------
# Ordering reads every declaration first, and must never be what breaks
# ---------------------------------------------------------------------------


def test_a_declaration_that_cannot_be_read_costs_only_itself(tmp_path):
    connector(tmp_path, 'alpha', 'optional: [zeta]\n')
    broken = tmp_path / 'connectors' / 'broken'
    broken.mkdir(parents=True)
    (broken / 'CONNECTOR.md').write_text('---\nname: [unclosed\n---\n', encoding='utf-8')
    connector(tmp_path, 'zeta')

    catalogue = load(roots=[tmp_path])

    assert order(tmp_path) == ['zeta', 'alpha']
    broken_one = catalogue.get('connector', 'broken')
    assert broken_one is not None and broken_one.status == SKIPPED
    assert handed(catalogue, 'alpha') == {'zeta': 'zeta'}


def test_a_list_written_as_a_single_name_is_skipped_with_a_reason_that_says_how(tmp_path):
    """`optional: zeta` would otherwise be iterated letter by letter."""
    connector(tmp_path, 'alpha', 'optional: zeta\n')
    connector(tmp_path, 'bravo', 'optional: [zeta]\n')
    connector(tmp_path, 'zeta')

    catalogue = load(roots=[tmp_path])

    alpha = catalogue.get('connector', 'alpha')
    assert alpha is not None and alpha.status == SKIPPED
    assert alpha.reason == '`optional:` must be a list of connector names, like `optional: [name]`'
    assert handed(catalogue, 'bravo') == {'zeta': 'zeta'}


def test_a_tool_s_lists_still_name_connectors_and_change_nothing_about_tool_order(tmp_path):
    connector(tmp_path, 'zeta')
    for name, lists in (('zeta_one', 'requires: [zeta]\n'), ('alpha_two', '')):
        folder = tmp_path / 'tools' / name
        folder.mkdir(parents=True)
        (folder / 'TOOL.md').write_text(
            f'---\nname: {name}\nnamespace: {name.split("_")[0]}\ndescription: a test tool\nenabled: true\n{lists}---\n\nBody.\n',
            encoding='utf-8',
        )
        (folder / 'tool.py').write_text(
            'from harry.sdk import Context, Registry\n\n\n'
            'def register(registry: Registry, context: Context) -> None:\n'
            f'    @registry.tool\n    def {name}() -> str:\n        return "ok"\n',
            encoding='utf-8',
        )

    catalogue = load(roots=[tmp_path])

    assert [c.name for c in catalogue if c.kind == 'tool'] == ['alpha_two', 'zeta_one']
    assert all(c.status == LOADED for c in catalogue if c.kind == 'tool'), [c.reason for c in catalogue]
