# pyright: reportPrivateUsage=false
#
# The gates this file tests are private helpers by design — nothing outside board.py
# calls `_live_clarifications` or `_merged_ids`. Testing them through the command
# surface alone would leave the git helpers untested, since every one of them returns
# empty outside a repo and the commands would look fine either way.
"""The board CLI's own tests.

The board is the only tool every feature passes through, so its gates get tested the
way a safety control does: by asserting the refusal, not the happy path.
"""

from __future__ import annotations

import pytest

import board


@pytest.fixture
def tmp_board(tmp_path, monkeypatch):
    """Point every board directory at a throwaway tree, and stub git out."""
    for name in ('FEATURES', 'STORIES', 'REQUIREMENTS', 'DECISIONS'):
        directory = tmp_path / name.lower()
        directory.mkdir()
        monkeypatch.setattr(board, name, directory)
    monkeypatch.setattr(board, 'ROOT', tmp_path)
    monkeypatch.setattr(board, 'git', lambda *args: '')
    return tmp_path


def all_ids(directory, kind):
    """Every board id of `kind` in a throwaway tree, read from the frontmatter."""
    return [
        board.read_frontmatter(path.read_text(encoding='utf-8'))['id']
        for path in sorted(directory.glob(f'{kind}-*.md'))
    ]


def only_id(directory, kind):
    """The single board id of `kind` in a throwaway tree, read from its frontmatter."""
    ids = all_ids(directory, kind)
    assert len(ids) == 1, f'expected one {kind}, found {len(ids)}'
    return ids[0]


def test_ids_carry_the_date_and_do_not_collide():
    ids = {board.new_id('FEAT') for _ in range(200)}
    assert len(ids) == 200
    assert all(board.ID_RE.match(item) for item in ids)


def test_slug_folds_accents_and_drops_punctuation():
    assert board.slugify('Le café, déjà vu!') == 'le-cafe-deja-vu'
    assert board.slugify('***') == 'untitled'


def test_frontmatter_round_trips():
    text = '---\nid: FEAT-260912-a1b2c3\nstatus: Backlog\n---\n\nbody\n'
    assert board.read_frontmatter(text)['status'] == 'Backlog'
    updated = board.set_frontmatter(text, 'status', 'In Progress')
    assert board.read_frontmatter(updated)['status'] == 'In Progress'
    # An absent key is inserted rather than silently dropped.
    assert board.read_frontmatter(board.set_frontmatter(text, 'track', 'story'))['track'] == 'story'


def test_list_field_reads_both_shapes():
    assert board.read_list('---\ntouches: []\n---\n', 'touches') == []
    assert board.read_list('---\ntouches: [a, b]\n---\n', 'touches') == ['a', 'b']


def test_a_comment_that_shows_the_marker_is_not_a_live_question(tmp_board):
    """The templates explain the marker by showing it. Masking is what stops that
    counting as an unresolved question and blocking every new feature forever."""
    assert board.main(['new-feature', 'A page that renders']) == 0
    feature_id = only_id(tmp_board / 'features', 'FEAT')
    assert board._live_clarifications(board.find(feature_id)) == []


def test_a_marker_wrapped_across_two_lines_still_blocks(tmp_board):
    assert board.main(['new-feature', 'A page that renders']) == 0
    path = next(tmp_board.glob('features/FEAT-*.md'))
    feature_id = only_id(tmp_board / 'features', 'FEAT')
    path.write_text(path.read_text() + '\n[NEEDS CLARIFICATION: settle this\nbefore the branch]\n')
    assert board.main(['clarifications', feature_id]) == 1


def test_done_is_never_typed(tmp_board, capsys):
    assert board.main(['new-feature', 'A page that renders']) == 0
    feature_id = only_id(tmp_board / 'features', 'FEAT')
    with pytest.raises(SystemExit):
        board.main(['set', feature_id, 'status', 'Done'])
    assert 'merge commit' in capsys.readouterr().err


def test_starting_a_second_feature_on_the_same_area_is_refused(tmp_board, capsys):
    board.main(['new-feature', 'The page renders', '--touches', 'modules/digest'])
    board.main(['new-feature', 'The page is capped', '--touches', 'modules/digest'])
    first, second = sorted(all_ids(tmp_board / 'features', 'FEAT'))

    assert board.main(['start', first]) == 0
    assert board.main(['start', second]) == 1
    assert 'also touches modules/digest' in capsys.readouterr().err

    # And deliberately, with --force, it goes through.
    assert board.main(['start', second, '--force']) == 0


def test_the_work_in_progress_cap_holds(tmp_board, capsys):
    for n in range(board.WIP_CAP + 1):
        board.main(['new-feature', f'Feature {n}', '--touches', f'modules/m{n}'])
    ids = sorted(all_ids(tmp_board / 'features', 'FEAT'))
    for feature_id in ids[: board.WIP_CAP]:
        assert board.main(['start', feature_id]) == 0
    assert board.main(['start', ids[board.WIP_CAP]]) == 1
    assert f'the cap is {board.WIP_CAP}' in capsys.readouterr().err


def test_the_story_track_writes_no_requirements_page(tmp_board):
    assert board.main(['new-feature', 'Cap the articles', '--track', 'story']) == 0
    assert list(tmp_board.glob('features/FEAT-*.md'))
    assert not list(tmp_board.glob('requirements/FEAT-*.md'))


def test_the_full_track_writes_one(tmp_board):
    assert board.main(['new-feature', 'The morning page', '--track', 'full']) == 0
    assert len(list(tmp_board.glob('requirements/FEAT-*.md'))) == 1


def test_a_story_registers_in_the_feature_frontmatter(tmp_board):
    """The list in the body and the list in the frontmatter must not disagree — a
    feature whose `stories: []` said none while the body listed a full set got broken
    down twice, in the repo this board was adapted from."""
    board.main(['new-feature', 'The morning page'])
    feature_id = only_id(tmp_board / 'features', 'FEAT')
    board.main(['new-story', 'Fetch the feeds', '--feature', feature_id])

    text = board.find(feature_id).read()
    story_id = only_id(tmp_board / 'stories', 'STORY')
    assert board.read_list(text, 'stories') == [story_id]
    assert story_id in text.partition('## Stories')[2]


def test_an_adr_registers_too(tmp_board):
    """Fixing the story path and leaving the ADR path is the exact slip `_register`
    exists to prevent, so both are asserted."""
    board.main(['new-feature', 'The morning page'])
    feature_id = only_id(tmp_board / 'features', 'FEAT')
    board.main(['new-adr', 'APScheduler over cron', '--feature', feature_id])

    text = board.find(feature_id).read()
    adr_id = only_id(tmp_board / 'decisions', 'ADR')
    assert board.read_list(text, 'decisions') == [adr_id]
    assert adr_id in text.partition('## Links')[2]


def test_check_ticks_the_nth_box(tmp_board, capsys):
    board.main(['new-feature', 'The morning page'])
    feature_id = only_id(tmp_board / 'features', 'FEAT')
    assert board.main(['check', feature_id, '1']) == 0
    assert '- [x]' in board.find(feature_id).read()
    assert board.main(['check', feature_id, '1']) == 0
    assert 'already checked' in capsys.readouterr().out


def test_a_bad_id_says_what_it_searched(tmp_board, capsys):
    with pytest.raises(SystemExit):
        board.find('not-an-id')
    assert 'is not a board id' in capsys.readouterr().err


def test_lanes_is_quiet_when_nothing_is_in_flight(tmp_board, capsys):
    assert board.main(['lanes']) == 0
    assert 'Free to start anything' in capsys.readouterr().out


def test_lanes_warns_about_an_undeclared_feature(tmp_board, capsys):
    board.main(['new-feature', 'The morning page'])
    feature_id = only_id(tmp_board / 'features', 'FEAT')
    board.main(['start', feature_id])
    board.main(['lanes'])
    out = capsys.readouterr().out
    assert 'undeclared' in out
    assert 'no branch' in out


def test_merged_features_report_done_without_the_board_storing_it(tmp_board, monkeypatch, capsys):
    board.main(['new-feature', 'The morning page'])
    feature_id = only_id(tmp_board / 'features', 'FEAT')
    monkeypatch.setattr(board, 'git', lambda *args: f'merge feat/{feature_id}-slug ({feature_id})')

    board.main(['list', 'features'])
    assert 'Done' in capsys.readouterr().out
    # Nothing was written. The frontmatter still says what it always said.
    assert board.read_frontmatter(board.find(feature_id).read())['status'] == 'Backlog'


# ---------------------------------------------------------------------------
# The rest of the command surface
# ---------------------------------------------------------------------------


def test_touches_shows_what_was_declared_and_replaces_it(tmp_board, capsys):
    board.main(['new-feature', 'The morning page', '--track', 'story'])
    feature_id = only_id(tmp_board / 'features', 'FEAT')

    board.main(['touches', feature_id])
    assert 'nothing declared' in capsys.readouterr().out

    board.main(['touches', feature_id, 'modules/news', 'modules/digest'])
    assert read_touches(tmp_board, feature_id) == ['modules/digest', 'modules/news']

    # Declaring again replaces rather than appends — a stale area would block a lane
    # nothing is actually working in.
    board.main(['touches', feature_id, 'core'])
    assert read_touches(tmp_board, feature_id) == ['core']


def read_touches(tmp_board, feature_id):
    return board.read_list(board.find(feature_id).read(), 'touches')


def test_a_note_is_dated_and_appended(tmp_board):
    board.main(['new-feature', 'The morning page'])
    feature_id = only_id(tmp_board / 'features', 'FEAT')
    board.main(['note', feature_id, 'Reflection: traceability 4/4'])
    board.main(['note', feature_id, 'Second thought'])

    notes = board.find(feature_id).read().partition('## Notes')[2]
    assert 'Reflection: traceability 4/4' in notes
    assert notes.index('Reflection') < notes.index('Second thought')


def test_a_subtask_lands_on_the_story(tmp_board):
    board.main(['new-feature', 'The morning page'])
    feature_id = only_id(tmp_board / 'features', 'FEAT')
    board.main(['new-story', 'Fetch the feeds', '--feature', feature_id])
    story_id = only_id(tmp_board / 'stories', 'STORY')

    board.main(['add-subtask', story_id, 'Record a 403 as a fixture'])
    assert 'Record a 403 as a fixture' in board.find(story_id).read().partition('## Subtasks')[2]


def test_stories_and_decisions_can_be_listed(tmp_board, capsys):
    board.main(['new-feature', 'The morning page'])
    feature_id = only_id(tmp_board / 'features', 'FEAT')
    board.main(['new-story', 'Fetch the feeds', '--feature', feature_id])
    board.main(['new-adr', 'APScheduler over cron', '--feature', feature_id])
    capsys.readouterr()

    board.main(['list', 'stories', '--feature', feature_id])
    assert 'Fetch the feeds' in capsys.readouterr().out

    board.main(['list', 'decisions'])
    assert 'APScheduler over cron' in capsys.readouterr().out

    # A filter that matches nothing says so rather than printing an empty table.
    board.main(['list', 'stories', '--status', 'Done'])
    assert 'nothing matches' in capsys.readouterr().out


def test_an_adr_is_accepted_and_then_superseded(tmp_board, capsys):
    board.main(['new-adr', 'APScheduler over cron'])
    board.main(['new-adr', 'The scheduler invokes claude -p'])
    first, second = sorted(
        board.read_frontmatter(p.read_text(encoding='utf-8'))['id']
        for p in sorted((tmp_board / 'decisions').glob('ADR-*.md'))
    )

    assert board.main(['set', first, 'status', 'Accepted']) == 0
    assert 'Accepted' in board.find(first).read().partition('## Status')[2]

    # Superseding without naming the successor is refused: an ADR that says only
    # "Superseded" leaves the reader with no way to find what replaced it.
    with pytest.raises(SystemExit):
        board.main(['set', first, 'status', 'Superseded'])
    assert 'requires --by' in capsys.readouterr().err

    assert board.main(['set', first, 'status', 'Superseded', '--by', second]) == 0
    text = board.find(first).read()
    assert board.read_frontmatter(text)['superseded_by'] == second
    assert second in text.partition('## Status')[2]


def test_a_story_cannot_be_started_and_a_bad_status_is_refused(tmp_board, capsys):
    board.main(['new-feature', 'The morning page'])
    feature_id = only_id(tmp_board / 'features', 'FEAT')
    board.main(['new-story', 'Fetch the feeds', '--feature', feature_id])
    story_id = only_id(tmp_board / 'stories', 'STORY')

    with pytest.raises(SystemExit):
        board.main(['start', story_id])
    assert 'only a feature is started' in capsys.readouterr().err

    with pytest.raises(SystemExit):
        board.main(['set', story_id, 'status', 'Shipped'])
    assert 'status must be one of' in capsys.readouterr().err

    with pytest.raises(SystemExit):
        board.main(['set', feature_id, 'status', 'In Progress'])
    assert 'board.py start' in capsys.readouterr().err


def test_new_story_refuses_a_parent_that_is_not_a_feature(tmp_board, capsys):
    board.main(['new-adr', 'APScheduler over cron'])
    adr_id = only_id(tmp_board / 'decisions', 'ADR')
    with pytest.raises(SystemExit):
        board.main(['new-story', 'Fetch the feeds', '--feature', adr_id])
    assert 'must be a FEAT id' in capsys.readouterr().err


def test_check_refuses_a_box_number_that_does_not_exist(tmp_board, capsys):
    board.main(['new-feature', 'The morning page'])
    feature_id = only_id(tmp_board / 'features', 'FEAT')
    with pytest.raises(SystemExit):
        board.main(['check', feature_id, '9'])
    assert 'asked for #9' in capsys.readouterr().err


def test_git_helpers_survive_not_being_in_a_repo(tmp_path, monkeypatch):
    """Every git call here is best-effort. A board that cannot read git still lists."""
    monkeypatch.setattr(board, 'ROOT', tmp_path)
    assert board.git('rev-parse', 'HEAD') == ''
    assert board.main_branch() == 'main'
    assert board._merged_ids() == set()
    assert board._branches() == {}
    assert board._worktrees() == {}
