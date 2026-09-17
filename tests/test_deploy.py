"""`make deploy` and `make rollback`, driven for real against a stub `docker`.

Going back to the previous version is the one command whose failure is discovered on the
morning you most need it not to be — and it is sixty lines of shell with four refusals in
it, none of which anything read before this file existed.

**The targets are run, not read.** `make` resolves the same variables, the same `$(shell)`
calls and the same recipes production uses; only `docker` is replaced, by a script on PATH
that records what it was asked to do and can be told to fail. A test that re-implemented
the tag logic in Python would prove the test right and say nothing about the Makefile.

`tests/test_digest_build.py` and `tests/test_remarkable_connector.py` already read the
Makefile, so treating it as something under test is not new here.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent

DOCKER_STUB = """#!/bin/sh
# Records the call and the one variable that decides what gets deployed, then obeys the
# script the test wrote: `fail` makes `compose up` exit non-zero, `images` lists the tags
# `image inspect` should find.
echo "$@ HARRY_TAG=${HARRY_TAG:-}" >> "$STUB_LOG"
case "$1 $2" in
  "image inspect")
    grep -qxF "$3" "$STUB_DIR/images" 2>/dev/null || exit 1 ;;
  "compose up")
    [ -f "$STUB_DIR/fail" ] && exit 1
    exit 0 ;;
esac
exit 0
"""


@pytest.fixture
def deployable(tmp_path):
    """A real git repository with Harry's Makefile in it, and a stub `docker` on PATH."""
    if shutil.which('make') is None or shutil.which('git') is None:
        pytest.skip('make and git are needed to run the targets')

    tree, stub_dir = tmp_path / 'tree', tmp_path / 'bin'
    tree.mkdir()
    stub_dir.mkdir()
    shutil.copy(REPO / 'Makefile', tree / 'Makefile')
    (tree / 'docker-compose.yml').write_text('services: {}\n', encoding='utf-8')
    (tree / 'Dockerfile').write_text('FROM scratch\n', encoding='utf-8')
    # As the real repository does. Without it the record `deploy` writes is itself an
    # untracked file, and the next `deploy` refuses the tree it just made dirty — which
    # is how this fixture found the interaction in the first place.
    (tree / '.gitignore').write_text('.deployed-tags\n', encoding='utf-8')

    stub = stub_dir / 'docker'
    stub.write_text(DOCKER_STUB, encoding='utf-8')
    stub.chmod(0o755)
    log = tmp_path / 'calls.log'

    # `-c` on every call: a machine with commit.gpgsign or a global core.hooksPath would
    # otherwise make these raise, and this file's whole point is that it runs the real
    # tools — an error here would read as a broken Makefile.
    git = ['git', '-c', 'commit.gpgsign=false', '-c', 'core.hooksPath=/dev/null']
    for command in (
        [*git, 'init', '-q', '-b', 'main'],
        [*git, 'config', 'user.email', 'test@example.com'],
        [*git, 'config', 'user.name', 'Test'],
        [*git, 'add', 'Makefile', 'docker-compose.yml', 'Dockerfile', '.gitignore'],
        [*git, 'commit', '-qm', 'first'],
    ):
        subprocess.run(command, cwd=tree, check=True, capture_output=True)

    class Deployable:
        path = tree
        tags = tree / '.deployed-tags'
        images = stub_dir / 'images'

        def make(self, target: str):
            environment = os.environ | {
                'PATH': f'{stub_dir}{os.pathsep}{os.environ["PATH"]}',
                'STUB_LOG': str(log),
                'STUB_DIR': str(stub_dir),
            }
            return subprocess.run(
                ['make', '--no-print-directory', target],
                cwd=tree,
                capture_output=True,
                text=True,
                env=environment,
            )

        def commit(self, name: str) -> str:
            (tree / name).write_text(name, encoding='utf-8')
            subprocess.run([*git, 'add', name], cwd=tree, check=True, capture_output=True)
            subprocess.run([*git, 'commit', '-qm', name], cwd=tree, check=True, capture_output=True)
            sha = subprocess.run(
                ['git', 'rev-parse', '--short', 'HEAD'], cwd=tree, capture_output=True, text=True, check=True
            ).stdout.strip()
            self.images.write_text((self.images.read_text() if self.images.exists() else '') + f'harry:{sha}\n')
            return sha

        def deployed(self) -> list[str]:
            return self.tags.read_text(encoding='utf-8').split() if self.tags.exists() else []

        def calls(self) -> list[str]:
            return log.read_text(encoding='utf-8').splitlines() if log.exists() else []

        def starts(self) -> list[str]:
            """Every call that brings a stack up, however it is spelled.

            Not `startswith('compose up')`: `up-dev` logs as `compose --profile dev up …`,
            so that filter made the dev stack invisible to every test here — including the
            one asserting that every start waits for healthy.
            """
            return [line for line in self.calls() if line.startswith('compose') and ' up ' in f' {line} ']

        def started_on(self) -> list[str]:
            return [line.split('HARRY_TAG=')[1] for line in self.starts()]

        def fail_the_next_up(self) -> None:
            (stub_dir / 'fail').touch()

    return Deployable()


# ---------------------------------------------------------------------------
# Deploying
# ---------------------------------------------------------------------------


def test_down_stops_the_browser_too(deployable):
    """The browser container runs with its syscall filtering relaxed, and it exists to serve
    Harry. Left running after `make down`, it outlives the only reason it is allowed to.

    Run, not read: the stub records what `docker` was actually asked to stop.
    """
    deployable.make('down')

    stopped = ' '.join(line for line in deployable.calls() if line.startswith(('compose stop', 'compose rm')))

    assert 'harry-browser' in stopped, f'`make down` asked docker only for: {stopped}'


def test_a_deploy_names_the_commit_records_it_and_starts_the_stack_on_it(deployable):
    sha = deployable.commit('one.txt')

    result = deployable.make('deploy')

    assert result.returncode == 0, result.stderr
    assert deployable.deployed() == [sha]
    assert deployable.started_on() == [sha]
    assert any(line.startswith(f'build -t harry:{sha} -t harry:latest .') for line in deployable.calls())


def test_a_deploy_is_refused_while_a_tracked_file_is_uncommitted(deployable):
    deployable.commit('one.txt')
    (deployable.path / 'one.txt').write_text('changed', encoding='utf-8')

    result = deployable.make('deploy')

    assert result.returncode != 0
    assert 'not clean' in result.stdout
    assert deployable.calls() == [], 'it built or deployed before refusing'


def test_a_deploy_is_refused_while_an_untracked_file_is_present(deployable):
    """`git diff HEAD` calls this clean, and the Dockerfile would have copied the file in.

    The tag would then name a commit the image is not built from — the one thing the tag
    exists to rule out.
    """
    deployable.commit('one.txt')
    (deployable.path / 'sneaky.py').write_text('print("in the image, not in git")', encoding='utf-8')

    result = deployable.make('deploy')

    assert result.returncode != 0
    assert 'sneaky.py' in result.stdout, 'the refusal did not say what was in the way'
    assert deployable.calls() == []


def test_a_deploy_that_never_comes_up_is_not_recorded_as_running(deployable):
    """`make versions` must not claim a version that failed to start."""
    first = deployable.commit('one.txt')
    deployable.make('deploy')
    deployable.commit('two.txt')
    deployable.fail_the_next_up()

    result = deployable.make('deploy')

    assert result.returncode != 0
    assert deployable.deployed() == [first], 'a failed deploy was recorded as the running version'


# ---------------------------------------------------------------------------
# Going back
# ---------------------------------------------------------------------------


def test_rollback_returns_to_the_previous_version_and_then_back_again(deployable):
    """Twice returns you to where you started — what you want when the rollback turns out
    not to have been the problem."""
    first = deployable.commit('one.txt')
    deployable.make('deploy')
    second = deployable.commit('two.txt')
    deployable.make('deploy')

    assert deployable.deployed() == [second, first]

    assert deployable.make('rollback').returncode == 0
    assert deployable.deployed() == [first, second]
    assert deployable.started_on()[-1] == first

    assert deployable.make('rollback').returncode == 0
    assert deployable.deployed() == [second, first]
    assert deployable.started_on()[-1] == second


def test_rollback_refuses_when_nothing_has_been_deployed_here(deployable):
    deployable.commit('one.txt')

    result = deployable.make('rollback')

    assert result.returncode != 0
    assert 'Nothing has been deployed' in result.stdout
    assert deployable.started_on() == []


def test_rollback_refuses_when_only_one_version_has_been_deployed(deployable):
    sha = deployable.commit('one.txt')
    deployable.make('deploy')

    result = deployable.make('rollback')

    assert result.returncode != 0
    assert 'Only one version' in result.stdout
    assert deployable.started_on() == [sha], 'it restarted the stack instead of refusing'


def test_rollback_refuses_when_the_previous_image_has_been_pruned_and_says_what_to_rebuild(deployable):
    """The failure that only shows up months later, when the thing you need is gone."""
    first = deployable.commit('one.txt')
    deployable.make('deploy')
    second = deployable.commit('two.txt')
    deployable.make('deploy')
    deployable.images.write_text(f'harry:{second}\n', encoding='utf-8')

    result = deployable.make('rollback')

    assert result.returncode != 0
    assert first in result.stdout, 'the refusal did not name the commit to rebuild from'
    assert deployable.deployed() == [second, first], 'it rewrote the record despite refusing'


# ---------------------------------------------------------------------------
# Starting
# ---------------------------------------------------------------------------


def test_make_up_runs_the_deployed_tag_rather_than_whatever_is_newest(deployable):
    """After a rollback, `make up` must not jump forward again."""
    first = deployable.commit('one.txt')
    deployable.make('deploy')
    deployable.commit('two.txt')
    deployable.make('deploy')
    deployable.make('rollback')

    deployable.make('up')

    assert deployable.started_on()[-1] == first


def test_make_up_falls_back_to_latest_on_a_machine_that_has_never_deployed(deployable):
    """What keeps a fresh clone starting with nothing configured — the bare-boot criterion."""
    deployable.commit('one.txt')

    assert deployable.make('up').returncode == 0
    assert deployable.started_on() == ['latest']


def test_a_rollback_that_never_comes_up_is_not_recorded_and_does_not_report_success(deployable):
    """The sibling of the deploy case, and it was still broken when that one was fixed.

    The recipe joined its four commands with `;`, so a failed `docker compose up` was
    followed by the record rewrite and by a green tick, and the target exited 0. That is
    the command you reach for on the one morning it matters, telling you it worked.
    """
    first = deployable.commit('one.txt')
    deployable.make('deploy')
    second = deployable.commit('two.txt')
    deployable.make('deploy')
    deployable.fail_the_next_up()

    result = deployable.make('rollback')

    assert result.returncode != 0, 'a rollback that never came up reported success'
    assert '✓' not in result.stdout
    assert deployable.deployed() == [second, first], 'the record says it went back, and it did not'


def test_every_start_waits_for_the_container_to_be_healthy(deployable):
    """`--wait` is the only thing that makes `compose up` fail when the container never
    becomes healthy. Without it `make deploy` records and announces a crash-looping image
    and `make up` returns 0 with Harry down — and the tests above would still pass, because
    a stub can be told to fail whatever flags it was given.

    It is also the only evidence for "the healthcheck the image already declares is what
    compose waits on", which nothing else asserts.
    """
    deployable.commit('one.txt')
    deployable.make('deploy')
    deployable.make('up')
    deployable.make('up-dev')
    deployable.make('rollback')

    starts = deployable.starts()
    assert len(starts) >= 3, f'not every target that starts a stack was exercised: {starts}'
    assert any('--profile dev' in line for line in starts), 'the dev stack was never started'
    for line in starts:
        assert '--wait' in line, f'a start that does not wait for healthy: {line}'


def test_stopping_a_stack_never_takes_its_data_with_it(deployable):
    """`down -v` deletes the volume: every rendered page, the store, and the De Tijd
    session. The recipes say so in a comment, and a comment is not a control.

    Neither `down` target was exercised by anything before this, so rewriting either as
    `docker compose down -v` left the whole suite green.
    """
    deployable.commit('one.txt')
    deployable.make('deploy')
    deployable.make('up-dev')

    deployable.make('down')
    deployable.make('down-dev')

    stops = [
        line
        for line in deployable.calls()
        if ' stop ' in f' {line} ' or ' down ' in f' {line} ' or ' rm ' in f' {line} '
    ]
    assert stops, 'neither stop target ran'
    for line in stops:
        assert ' -v' not in f' {line} ', f'a stop that deletes the data volume: {line}'
        assert '--volumes' not in line, f'a stop that deletes the data volume: {line}'
