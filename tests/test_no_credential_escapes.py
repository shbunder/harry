"""The three places a credential must never be, and a check for each.

Harry holds three all-or-nothing secrets — a tablet token with no scopes, an iCloud app
password, and a live logged-in newspaper session. `.claude/rules/secrets-and-config.md`
says where they live; this says where they do not.

**The committed compose file** is checked in the gate, because that is the file somebody
edits at a terminal to make one thing work and then commits.

**The image** is checked under `live`, because the truth of it depends on something the
repository does not track: a built `harry:latest`. Run it with `make test-live` after
`make image`. The `.dockerignore` lines it verifies are otherwise a control nothing
executes — they are three globs, and a glob that matches nothing looks exactly like a glob
that matches everything it should.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).parent.parent
COMPOSE = REPO / 'docker-compose.yml'
IMAGE = 'harry:latest'

LOOKS_LIKE_A_SECRET = re.compile(
    r'xox[baprs]-[A-Za-z0-9-]{10,}'  # a Slack bot or user token
    r'|[a-z]{4}-[a-z]{4}-[a-z]{4}-[a-z]{4}'  # an Apple app-specific password
    r'|\b[A-Za-z0-9_-]{40,}\b',  # a reMarkable device token, and most bearer tokens
)
"""What a real credential looks like if one is pasted into a committed file.

Shapes rather than key names, because the failure this catches is somebody setting a value
on a key that is supposed to be empty — the key name would look entirely correct.
"""


# ---------------------------------------------------------------------------
# The committed compose file
# ---------------------------------------------------------------------------


def test_the_committed_compose_file_carries_no_credential():
    """Every value in it is a port, a path, a boolean or a name — never a secret."""
    found = LOOKS_LIKE_A_SECRET.findall(COMPOSE.read_text(encoding='utf-8'))

    assert found == [], f'{COMPOSE.name} contains something shaped like a credential: {found}'


def test_neither_stack_reaches_a_credential_file_from_inside_the_image():
    """Secrets arrive as injected variables; nothing mounts a file that holds one.

    A bind mount of a `.env.local` would put a credential inside the container at a path,
    which is the one route the `Dockerfile` is written to avoid. Only the data volumes are
    mounted, and each stack has its own.
    """
    compose = yaml.safe_load(COMPOSE.read_text(encoding='utf-8'))

    mounted = {name: service.get('volumes') or [] for name, service in compose['services'].items()}
    for name, volumes in mounted.items():
        for volume in volumes:
            source = volume.split(':')[0] if isinstance(volume, str) else volume.get('source', '')
            assert source in compose['volumes'], f'{name} mounts {source!r}, which is not one of the named volumes'

    assert mounted['harry'] != mounted['harry-dev'], 'both stacks mount the same volume, so neither is separate'


def test_each_stack_pins_its_own_port_and_data_directory_on_the_service():
    """`environment:` outranks `env_file:`, and that is what makes the published port true.

    Left to a file, a stray `HARRY_PORT` moves the port Harry listens on while compose
    still publishes the old one — and the healthcheck reads the same variable, so the
    container reports healthy while nothing can reach it.
    """
    compose = yaml.safe_load(COMPOSE.read_text(encoding='utf-8'))

    for name, service in compose['services'].items():
        environment = service['environment']
        published = str(service['ports'][0]).split(':')[0]
        assert str(environment['HARRY_PORT']) == published, (
            f'{name} publishes {published} and tells Harry to listen on {environment["HARRY_PORT"]}'
        )
        assert environment['HARRY_DATA_DIR'] == '/data', f'{name} points its data directory off the volume'


def test_only_the_real_stack_keeps_the_clock():
    """Two watchdogs on one machine is the failure the second stack is shaped around."""
    compose = yaml.safe_load(COMPOSE.read_text(encoding='utf-8'))
    keeping_time = {
        name
        for name, service in compose['services'].items()
        if str(service['environment']['HARRY_SCHEDULER_ENABLED']).lower() == 'true'
    }

    assert keeping_time == {'harry'}, f'{keeping_time or "nothing"} keeps the clock; it must be exactly the real stack'


def test_the_dev_stack_is_behind_a_profile_so_make_up_cannot_start_it():
    """`make up` starts the real stack only. The profile is the whole of that guarantee."""
    compose = yaml.safe_load(COMPOSE.read_text(encoding='utf-8'))

    assert compose['services']['harry-dev']['profiles'] == ['dev']
    assert 'profiles' not in compose['services']['harry'], (
        'the real stack is behind a profile, so `make up` starts nothing'
    )


# ---------------------------------------------------------------------------
# The built image
# ---------------------------------------------------------------------------


def in_the_image(*command: str) -> str:
    return subprocess.run(
        ['docker', 'run', '--rm', '--entrypoint', 'sh', IMAGE, '-c', *command],
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    ).stdout


@pytest.fixture
def built_image():
    """Skips unless `harry:latest` is on this machine — it is not a tracked artefact."""
    if shutil.which('docker') is None:
        pytest.skip('docker is not installed here')
    present = subprocess.run(['docker', 'image', 'inspect', IMAGE], capture_output=True, text=True)
    if present.returncode != 0:
        pytest.skip(f'{IMAGE} has not been built here — run `make image` first')
    return json.loads(present.stdout)[0]


@pytest.mark.live
def test_no_credential_file_reached_the_image(built_image):
    """`.dockerignore` excludes them; this is the line that proves the exclusion worked.

    Depends on a built `harry:latest` and on it having been built from this tree — a stale
    image would answer about a `.dockerignore` that is no longer the one in the repository.

    The same `find` also looks for a file that is certainly there, and the test fails if it
    does not come back. An empty result is the pass condition here, and an empty result is
    also what a `find` that could not read the filesystem returns — so without the decoy
    this test would go green on a broken command, which is the one way it could matter and
    not say so.
    """
    decoy = '/app/.harry/connectors/weather/.env'
    found = in_the_image(
        r'find / -xdev \( -name ".env.local" -o -name ".env.*.local" -o -name "storage-state*.json" '
        rf'-o -path "{decoy}" \) 2>/dev/null'
    ).split()

    assert decoy in found, f'the search itself came back empty, so it proves nothing: {found}'
    assert [f for f in found if f != decoy] == [], f'the image carries credential files: {found}'


@pytest.mark.live
def test_the_committed_capability_env_files_shipped_with_their_secrets_empty(built_image):
    """Those `.env` files are in the image by design. Every secret key in them is blank."""
    filled = [
        line
        for line in in_the_image('grep -H "." /app/.harry/*/*/.env 2>/dev/null').splitlines()
        if (value := line.partition('=')[2].strip())
        and not line.split(':', 1)[1].startswith('#')
        and LOOKS_LIKE_A_SECRET.search(value)
    ]

    assert filled == [], f'a committed capability .env shipped with a value that looks like a credential: {filled}'


@pytest.mark.live
def test_the_image_is_handed_no_configuration_beyond_a_port_and_a_path(built_image):
    """The image carries code. Everything else arrives from compose at run time.

    Anything else baked in here is configuration that would travel with the image to a
    machine it was not meant for.
    """
    baked = sorted(variable for variable in built_image['Config']['Env'] if variable.startswith('HARRY_'))

    assert baked == ['HARRY_DATA_DIR=/data', 'HARRY_PORT=7430'], baked
