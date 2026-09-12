"""The two scripts the gate runs.

Both are controls, so both get tested in the direction that matters: the guard is made
to fail, and the search is made to miss. A guard only ever tested on clean input is the
defect `.claude/rules/inert-controls.md` describes.
"""

from __future__ import annotations

import subprocess

import check_no_board_refs
import query_lessons

# One real id on the board, and one that is only id-shaped. The guard must tell them
# apart: the board's own tests are full of the second kind.
REAL = 'FEAT-260912-a1b2c3'
FABRICATED = 'FEAT-991231-ffffff'


def _repo(tmp_path, files: dict[str, str], *, board=(f'features/{REAL}-the-page.md',)):
    """A real git repo with real files, because the guard reads `git ls-files`.

    `board` seeds the items the guard resolves ids against. Without it every id is
    fabricated and nothing can be flagged.
    """
    subprocess.run(['git', 'init', '-q', str(tmp_path)], check=True)
    for name in board:
        path = tmp_path / 'project' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('---\n', encoding='utf-8')
    for name, body in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding='utf-8')
    subprocess.run(['git', '-C', str(tmp_path), 'add', '-A'], check=True)
    return tmp_path


# ---------------------------------------------------------------------------
# The board-reference guard
# ---------------------------------------------------------------------------


def test_the_guard_fails_on_a_real_board_id_in_source(tmp_path, monkeypatch, capsys):
    repo = _repo(tmp_path, {'packages/harry/src/harry/x.py': f'# Added for {REAL}\nX = 1\n'})
    monkeypatch.setattr(check_no_board_refs, 'ROOT', repo)

    assert check_no_board_refs.main([]) == 1
    err = capsys.readouterr().err
    assert REAL in err
    assert 'x.py:1' in err


def test_an_id_that_matches_nothing_on_the_board_is_test_data(tmp_path, monkeypatch):
    """This is why the guard resolves rather than pattern-matches. Without it, the
    board's own test suite could not contain a single example id, and the guard would
    have gone red on this repo's first commit."""
    repo = _repo(tmp_path, {'tests/test_x.py': f"ID = '{FABRICATED}'\n"})
    monkeypatch.setattr(check_no_board_refs, 'ROOT', repo)
    assert check_no_board_refs.main([]) == 0


def test_an_empty_board_flags_nothing(tmp_path, monkeypatch, capsys):
    repo = _repo(tmp_path, {'packages/harry/src/harry/x.py': f'# {REAL}\n'}, board=())
    monkeypatch.setattr(check_no_board_refs, 'ROOT', repo)
    assert check_no_board_refs.main([]) == 0
    assert 'board is empty' in capsys.readouterr().out


def test_two_references_on_one_line_are_both_reported(tmp_path, monkeypatch, capsys):
    second = 'STORY-260912-d4e5f6'
    repo = _repo(
        tmp_path,
        {'packages/harry/src/harry/x.py': f'# {REAL} and {second}\n'},
        board=(f'features/{REAL}-the-page.md', f'stories/{second}-fetch.md'),
    )
    monkeypatch.setattr(check_no_board_refs, 'ROOT', repo)
    assert check_no_board_refs.main([]) == 1
    err = capsys.readouterr().err
    assert REAL in err and second in err


def test_the_guard_passes_on_clean_source(tmp_path, monkeypatch):
    repo = _repo(tmp_path, {'packages/harry/src/harry/x.py': '# APScheduler, not cron: no cron daemon here\nX = 1\n'})
    monkeypatch.setattr(check_no_board_refs, 'ROOT', repo)
    assert check_no_board_refs.main([]) == 0


def test_the_board_and_the_docs_may_say_the_id(tmp_path, monkeypatch):
    """`project/` and `docs/` are the record of why. They cite ids by design."""
    repo = _repo(
        tmp_path,
        {
            'project/board.py': f'# {REAL}\n',
            'docs/operating.md': REAL,
            '.claude/rules/x.md': REAL,
        },
    )
    monkeypatch.setattr(check_no_board_refs, 'ROOT', repo)
    assert check_no_board_refs.main([]) == 0


def test_a_markdown_file_in_source_is_not_scanned(tmp_path, monkeypatch):
    """Only the suffixes in SOURCE_SUFFIXES are code. A stray note is not."""
    repo = _repo(tmp_path, {'packages/notes.md': REAL})
    monkeypatch.setattr(check_no_board_refs, 'ROOT', repo)
    assert check_no_board_refs.main([]) == 0


# ---------------------------------------------------------------------------
# The lessons search
# ---------------------------------------------------------------------------


LESSON = """---
id: FEAT-260912-a1b2c3
title: The morning page lands on the tablet
---

# body

## Lessons Learned

- **What worked** — pinning rmapi exactly.
- **What to do differently** — the reMarkable push needs a retry ceiling.
"""


def _board(tmp_path, monkeypatch, files: dict[str, str]):
    for name, body in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding='utf-8')
    monkeypatch.setattr(query_lessons, 'BOARD', tmp_path)
    return tmp_path


def test_lessons_rank_by_how_often_the_terms_appear(tmp_path, monkeypatch, capsys):
    # The strong one says "remarkable" twice, the weak one once. Neither may say it
    # zero times: a lesson that matches nothing is filtered out rather than ranked
    # last, so a zero-hit control would prove nothing about the ordering.
    strong = LESSON.replace('- **What worked**', '- **What worked** — the reMarkable client\n- **Also**')
    weak = LESSON.replace('a1b2c3', 'd4e5f6')
    _board(
        tmp_path,
        monkeypatch,
        {
            'features/FEAT-260912-a1b2c3-strong.md': strong,
            'features/FEAT-260911-d4e5f6-weak.md': weak,
        },
    )
    assert query_lessons.main(['remarkable']) == 0
    out = capsys.readouterr().out
    assert 'a1b2c3' in out and 'd4e5f6' in out
    assert out.index('a1b2c3') < out.index('d4e5f6')


def test_an_empty_board_is_not_an_error(tmp_path, monkeypatch, capsys):
    """Treating "no lessons yet" as a failure teaches people to skip the step."""
    _board(tmp_path, monkeypatch, {})
    assert query_lessons.main(['remarkable']) == 0
    assert 'No lessons' in capsys.readouterr().out


def test_a_feature_with_no_lessons_section_is_skipped(tmp_path, monkeypatch, capsys):
    _board(tmp_path, monkeypatch, {'features/FEAT-260912-a1b2c3-x.md': '---\ntitle: X\n---\n\nno lessons here\n'})
    assert query_lessons.main([]) == 0
    assert 'No lessons' in capsys.readouterr().out


def test_since_filters_by_the_id_date(tmp_path, monkeypatch, capsys):
    _board(tmp_path, monkeypatch, {'features/FEAT-260912-a1b2c3-x.md': LESSON})
    assert query_lessons.main(['rmapi', '--since', '260913']) == 0
    assert 'No lessons' in capsys.readouterr().out

    assert query_lessons.main(['rmapi', '--since', '260901']) == 0
    assert 'a1b2c3' in capsys.readouterr().out


def test_top_caps_the_output_and_says_so(tmp_path, monkeypatch, capsys):
    files = {f'features/FEAT-2609{n:02d}-a1b2c{n}-x.md': LESSON for n in range(10, 14)}
    _board(tmp_path, monkeypatch, files)
    assert query_lessons.main(['rmapi', '--top', '2']) == 0
    assert 'and 2 more' in capsys.readouterr().out
