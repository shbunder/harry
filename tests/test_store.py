"""What Harry remembers between restarts.

Small on purpose, and every failure path is a real one: a file that is not JSON, a file
that is JSON but not this file, and a directory that cannot be written. Each of those
happens on a real machine, and each has to leave Harry running.
"""

from __future__ import annotations

import datetime as dt
import json
import logging

from harry.store import Store

MORNING = dt.datetime(2026, 9, 13, 6, 45, tzinfo=dt.UTC)


def test_what_a_job_did_survives_a_restart(tmp_path):
    """The whole reason this is on disk. In memory a restart would lose every completion and
    the watchdog would report a missed deadline for a page delivered an hour earlier."""
    path = tmp_path / 'jobs.json'
    Store(path).mark_finished('morning-page', MORNING)

    assert Store(path).last_finished('morning-page') == MORNING


def test_a_job_nothing_is_known_about_has_no_time(tmp_path):
    assert Store(tmp_path / 'jobs.json').last_finished('morning-page') is None


def test_what_has_already_been_reported_survives_a_restart(tmp_path):
    path = tmp_path / 'jobs.json'
    Store(path).mark_reported('morning-page', dt.date(2026, 9, 13))

    assert Store(path).reported('morning-page') == dt.date(2026, 9, 13)


def test_two_jobs_do_not_share_a_record(tmp_path):
    store = Store(tmp_path / 'jobs.json')
    store.mark_finished('morning-page', MORNING)

    assert store.last_finished('weekly-reading') is None


def test_the_file_is_something_a_person_can_read(tmp_path):
    """A file somebody can `cat` while wondering why the watchdog is quiet is worth more
    than an index. That is the whole argument against SQLite here, so it is asserted."""
    path = tmp_path / 'jobs.json'
    store = Store(path)
    store.mark_finished('morning-page', MORNING)
    store.mark_reported('morning-page', dt.date(2026, 9, 12))

    written = json.loads(path.read_text(encoding='utf-8'))

    assert written == {'jobs': {'morning-page': {'finished': MORNING.isoformat(), 'reported': '2026-09-12'}}}


# ---------------------------------------------------------------------------
# When the file is not what it should be
# ---------------------------------------------------------------------------


def test_a_file_that_is_not_json_starts_empty_and_says_so(tmp_path, caplog):
    """A false alarm at the next check is the safe direction. Refusing to start would take
    Harry down to protect a timestamp."""
    path = tmp_path / 'jobs.json'
    path.write_text('{ this is not json', encoding='utf-8')

    with caplog.at_level(logging.WARNING, logger='harry.store'):
        store = Store(path)

    assert store.last_finished('morning-page') is None
    assert 'starting with an empty record' in caplog.text


def test_json_that_is_not_this_file_starts_empty(tmp_path):
    """Somebody's unrelated file at the same path. Not an error, just nothing known."""
    path = tmp_path / 'jobs.json'
    path.write_text('[1, 2, 3]', encoding='utf-8')

    assert Store(path).as_dict() == {}


def test_a_time_that_will_not_parse_reads_as_nothing_known(tmp_path):
    """Hand-edited, or written by a version that stored it differently. The watchdog then
    alerts, which is the safe direction."""
    path = tmp_path / 'jobs.json'
    path.write_text(json.dumps({'jobs': {'morning-page': {'finished': 'yesterday', 'reported': 'soon'}}}))
    store = Store(path)

    assert store.last_finished('morning-page') is None
    assert store.reported('morning-page') is None


def test_a_directory_that_cannot_be_written_says_so_and_does_not_break_the_caller(tmp_path, caplog):
    """A read-only data volume is a real problem somebody should hear about, and it is not a
    reason for the job that just finished to fail."""
    locked = tmp_path / 'locked'
    locked.mkdir()
    locked.chmod(0o500)
    store = Store(locked / 'jobs.json')

    try:
        with caplog.at_level(logging.WARNING, logger='harry.store'):
            store.mark_finished('morning-page', MORNING)
    finally:
        locked.chmod(0o700)

    assert 'could not write' in caplog.text
    # Still true in memory, so the watchdog behaves for the rest of this process.
    assert store.last_finished('morning-page') == MORNING


def test_the_file_is_created_with_its_parent(tmp_path):
    """The data volume on a fresh machine has nothing in it."""
    store = Store(tmp_path / 'data' / 'nested' / 'jobs.json')
    store.mark_finished('morning-page', MORNING)

    assert (tmp_path / 'data' / 'nested' / 'jobs.json').is_file()


def test_as_dict_hands_back_a_copy(tmp_path):
    """Anything that wants to look at what is remembered should not be able to change it by
    accident."""
    store = Store(tmp_path / 'jobs.json')
    store.mark_finished('morning-page', MORNING)

    taken = store.as_dict()
    taken['morning-page']['finished'] = 'tampered'

    assert store.last_finished('morning-page') == MORNING
