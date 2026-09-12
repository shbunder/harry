"""The scaffolding is wired.

Cheap checks that catch the failure where a package is declared and never installed, or
a version drifts between two files that both claim it.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import harry

ROOT = Path(__file__).parent.parent


def test_the_package_imports_and_carries_a_version():
    assert harry.__version__


def test_the_declared_version_and_the_package_version_agree():
    declared = tomllib.loads((ROOT / 'packages' / 'harry' / 'pyproject.toml').read_text())
    assert declared['project']['version'] == harry.__version__


def test_the_workspace_lists_every_package_directory():
    """A package added under `packages/` but never wired is installed by nothing."""
    root = tomllib.loads((ROOT / 'pyproject.toml').read_text())
    assert root['tool']['uv']['workspace']['members'] == ['packages/*']
    on_disk = {p.name for p in (ROOT / 'packages').iterdir() if (p / 'pyproject.toml').exists()}
    assert on_disk, 'packages/ holds no package'


def test_no_board_ids_leak_into_source():
    """`make lint` runs this too; having it in the suite means a `make test` catches it."""
    import check_no_board_refs

    assert check_no_board_refs.main([]) == 0
