"""The suite answers the same on every machine.

`tests/capability_copy.py` exists for one reason, and this file is the reason it stays true.
"""

from __future__ import annotations

import re
from pathlib import Path

from .capability_copy import copy_capability

REPO = Path(__file__).parent.parent
TESTS = Path(__file__).parent


def test_a_copied_capability_leaves_this_machines_settings_behind(tmp_path):
    """The whole point. `.env.local` is read ahead of the committed `.env`, so a copy that
    carries one is a test configured by whoever ran it."""
    source = tmp_path / 'connectors' / 'example'
    source.mkdir(parents=True)
    (source / 'CONNECTOR.md').write_text('---\nname: example\nkind: connector\n---\n', encoding='utf-8')
    (source / '.env').write_text('FEEDS=vrt,bbc\n', encoding='utf-8')
    (source / '.env.local').write_text('FEEDS=vrt,bbc,tijd\n', encoding='utf-8')
    (source / 'connector.py').write_text('def register(registry, context): ...\n', encoding='utf-8')
    (source / '__pycache__').mkdir()
    (source / '__pycache__' / 'connector.cpython-312.pyc').write_bytes(b'stale')

    copied = copy_capability(source, tmp_path / 'root' / 'connectors' / 'example')

    assert sorted(item.name for item in copied.iterdir()) == ['.env', 'CONNECTOR.md', 'connector.py']
    assert (copied / '.env').read_text(encoding='utf-8') == 'FEEDS=vrt,bbc\n'
    assert not (copied / '.env.local').exists(), 'this machine came along'
    assert not (copied / '__pycache__').exists(), 'a stale .pyc came along'


def test_the_committed_env_does_come_along(tmp_path):
    """The other half: `.env` is generated from the declaration and committed, so it is part
    of what a capability *is*. Ignoring both files would make the test meaningless."""
    source = tmp_path / 'connectors' / 'example'
    source.mkdir(parents=True)
    (source / '.env').write_text('PLACE=Leuven\n', encoding='utf-8')

    copied = copy_capability(source, tmp_path / 'root' / 'connectors' / 'example')

    assert (copied / '.env').read_text(encoding='utf-8') == 'PLACE=Leuven\n'


def test_no_test_copies_a_capability_any_other_way():
    """Eight call sites moved onto the helper, and this is what stops a ninth appearing.

    Delete a call to `copy_capability`, put the direct copy back, and this fails — which is
    the only thing making the move stick.

    This file excludes itself: the pattern it looks for is written down here, in the line
    above, and a guard that trips on its own definition is a guard nobody can keep.
    """
    reaching = re.compile(r'copytree\([^)]*REPO\s*/\s*[\'"]\.harry[\'"]', re.S)
    offenders = [
        path.name
        for path in sorted(TESTS.glob('test_*.py'))
        if path.name != Path(__file__).name and reaching.search(path.read_text(encoding='utf-8'))
    ]

    assert offenders == [], f'{offenders} copy .harry/ directly — use copy_capability from capability_copy'


def test_a_local_env_beside_a_capability_never_reaches_a_loaded_test(tmp_path):
    """The failure this exists for, made to happen, all the way through `load()`.

    Copying the real weather connector into a staging folder, planting a `.env.local` beside
    it there, then taking the copy a test would take: the connector that comes up must be
    pointed at the committed place, not the planted one.

    Walking the real `.harry/` tree and asserting no `.env.local` came along would pass on a
    machine that has none — which is every machine except the one where this was found.
    """
    from harry.loader import load

    staged = copy_capability(REPO / '.harry' / 'connectors' / 'weather', tmp_path / 'staged')
    (staged / '.env.local').write_text('PLACE=Reykjavik\nLATITUDE=64.15\n', encoding='utf-8')

    root = tmp_path / 'root'
    copy_capability(staged, root / 'connectors' / 'weather')

    assert not (root / 'connectors' / 'weather' / '.env.local').exists()
    found = load([root]).get('connector', 'weather')
    assert found is not None and found.target is not None
    assert found.target.place == 'Leuven', 'the machine configured the test'
