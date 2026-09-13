"""The scaffolding is wired.

Cheap checks that catch the failure where a package is declared and never installed, or
a version drifts between two files that both claim it.
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

import harry

ROOT = Path(__file__).parent.parent


def test_the_package_imports_and_carries_a_version():
    assert harry.__version__


def test_the_declared_version_and_the_package_version_agree():
    declared = tomllib.loads((ROOT / 'pyproject.toml').read_text())
    assert declared['project']['version'] == harry.__version__


def test_the_package_is_where_every_tool_is_told_it_is():
    """Four path rosters name the source directory — the build, ruff, coverage and
    pyright. They disagreed once already, and a disagreement is silent: one tool simply
    stops looking at a file."""
    root = tomllib.loads((ROOT / 'pyproject.toml').read_text())
    assert root['tool']['hatch']['build']['targets']['wheel']['packages'] == ['src/harry']
    assert 'src' in root['tool']['ruff']['src']
    assert 'src/harry' in root['tool']['coverage']['run']['source']

    pyright = json.loads((ROOT / 'pyrightconfig.json').read_text())
    assert 'src' in pyright['include'] and 'src' in pyright['extraPaths']

    assert (ROOT / 'src' / 'harry' / '__init__.py').is_file()


def test_no_board_ids_leak_into_source():
    """`make lint` runs this too; having it in the suite means a `make test` catches it."""
    import check_no_board_refs

    assert check_no_board_refs.main([]) == 0
