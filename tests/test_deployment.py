"""What the two stacks promise, and what the image must not carry.

`docker-compose.yml` is the whole of Harry's deployment, so the promises a reader takes
from it are worth holding to something that runs: the two stacks cannot collide on a port
or a volume, only one of them keeps the clock, only one starts by default, the real one
names a version, and no credential is written down in it.

**The compose file** is checked in the gate. It is the file somebody edits at a terminal to
make one thing work, and then commits.

**The image** is checked under `live`, because the truth of it depends on something the
repository does not track: a built `harry:latest`. Run it with `make test-live` after
`make image`. The `.dockerignore` lines it verifies are otherwise a control nothing
executes — they are globs, and a glob that matches nothing looks exactly like a glob that
matches everything it should.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from fnmatch import fnmatch
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


def sources(service: dict) -> set[str]:
    """The named volumes a service mounts. Empty is a finding, not a pass."""
    return {
        (volume.split(':')[0] if isinstance(volume, str) else volume.get('source', ''))
        for volume in service.get('volumes') or []
    }


def test_each_stack_keeps_its_data_on_a_named_volume_of_its_own():
    """Secrets arrive as injected variables; nothing mounts a file that holds one. And the
    data lives on a volume, which is what makes it outlive the container.

    **Every assertion here is positive first.** An earlier version compared the two
    services' mount lists for inequality, which passes when one of them mounts nothing at
    all — deleting the real stack's whole `volumes:` block left the suite green, and the
    store, every rendered page and the De Tijd session would have died with the container.
    """
    compose = yaml.safe_load(COMPOSE.read_text(encoding='utf-8'))
    mounted = {name: sources(service) for name, service in compose['services'].items()}

    for name, found in mounted.items():
        assert found, f'{name} mounts nothing, so everything it writes dies with the container'
        assert found <= set(compose['volumes']), f'{name} mounts {found - set(compose["volumes"])}, not a named volume'

    assert not (mounted['harry'] & mounted['harry-dev']), (
        f'both stacks mount {mounted["harry"] & mounted["harry-dev"]} — `down -v` on dev would take the real store'
    )


def test_the_two_stacks_cannot_collide_on_a_port_a_name_or_a_volume():
    """The promise this module's docstring makes, asserted rather than described.

    Each of these was checked only against itself before: every service agreed with its own
    published port, and nothing noticed when both services published 7430 under the same
    container name.
    """
    compose = yaml.safe_load(COMPOSE.read_text(encoding='utf-8'))
    services = compose['services']

    for field, got in (
        ('container_name', [s['container_name'] for s in services.values()]),
        ('published port', [str(s['ports'][0]) for s in services.values()]),
        ('HARRY_PORT', [str(s['environment']['HARRY_PORT']) for s in services.values()]),
    ):
        assert len(set(got)) == len(services), f'two services share a {field}: {got}'


def test_neither_stack_is_handed_a_provider_credential():
    """`no-model-calls.md` is scoped to this file, and the comment beside `environment:`
    claims the point. A comment is not a control.

    This is the block a credential would be added to — it is where every other variable
    the container gets is written down, and adding one line here is the easiest way for
    Harry to acquire a route to a model.
    """
    compose = yaml.safe_load(COMPOSE.read_text(encoding='utf-8'))

    # Matched against the parsed document rather than the file's text: the comment beside
    # `environment:` cites `.claude/rules/no-model-calls.md`, and a raw scan flags the
    # rule's own path. The keys and the mounts are what actually reach the container.
    forbidden = ('ANTHROPIC', 'OPENAI', 'CLAUDE', 'GEMINI', 'MISTRAL', 'COHERE', 'HUGGINGFACE')

    def offends(text: str) -> bool:
        return any(word in text.upper() for word in forbidden)

    for name, service in compose['services'].items():
        for key in service.get('environment') or {}:
            assert not offends(key), f'{name} is handed {key}, which is a route to a model'
        for entry in service.get('env_file') or []:
            path = entry if isinstance(entry, str) else entry['path']
            assert not offends(path), f"{name} reads {path}, which is somebody's model credentials"
        assert not any(offends(source) for source in sources(service)), f'{name} mounts a model credential'


def test_both_stacks_come_back_by_themselves():
    """`restart: unless-stopped` is what puts Harry back after a crash and after a reboot.

    Nothing read these two lines before, and they are the whole of the criterion about
    surviving a restart of the machine.
    """
    compose = yaml.safe_load(COMPOSE.read_text(encoding='utf-8'))

    for name, service in compose['services'].items():
        assert service.get('restart') == 'unless-stopped', f'{name} does not come back on its own'


def test_the_dev_stack_reads_its_own_credentials_and_never_the_real_one_s():
    """The reMarkable token has no scopes and no read-only mode, so a dev stack reading the
    real `.env.local` is a dev stack that can rewrite every document on the tablet.

    Pointing dev at `.env.local` used to leave the suite green, which made the comment
    beside it the only thing standing between a test run and the real device.
    """
    compose = yaml.safe_load(COMPOSE.read_text(encoding='utf-8'))

    def local_files(service: dict) -> set[str]:
        return {(entry if isinstance(entry, str) else entry['path']) for entry in service['env_file']} - {'.env'}

    real, dev = local_files(compose['services']['harry']), local_files(compose['services']['harry-dev'])

    assert real and dev, 'a stack with no machine-local env file has nowhere for a credential to come from'
    assert not (real & dev), f'both stacks read {real & dev}, so dev holds the real tablet token'


def test_the_committed_defaults_are_read_before_the_machine_s_own_file():
    """The order in `env_file:` is the whole of how a credential reaches the container.

    Reversed, the committed `HARRY_API_TOKEN=` shadows the operator's real one and Harry
    resolves to "nobody is authorised" — the 06:30 task gets a 401 and no page is built.
    The comment above the block says the order matters, and a comment is not a control.
    """
    compose = yaml.safe_load(COMPOSE.read_text(encoding='utf-8'))

    for name, service in compose['services'].items():
        paths = [entry if isinstance(entry, str) else entry['path'] for entry in service['env_file']]
        assert paths[0] == '.env', f'{name} reads {paths[0]} before the committed defaults'
        assert len(paths) == 2, f'{name} reads {paths}, and only two files have a defined precedence'


def test_a_new_dockerignore_pattern_actually_excludes_what_it_names():
    """`.env.*.local` matches nothing on this machine, so the live image test cannot see it.

    A glob that matches nothing looks exactly like a glob that matches everything it
    should — this module's own docstring. These are the names a credential would arrive
    under, checked against the patterns rather than against the filesystem.
    """
    patterns = [
        line.strip()
        for line in (REPO / '.dockerignore').read_text(encoding='utf-8').splitlines()
        if line.strip() and not line.startswith('#')
    ]

    for name in (
        '.env.local',
        '.env.dev.local',
        '.harry/connectors/icloud/.env.local',
        '.harry/connectors/icloud/.env.dev.local',
        'storage-state.json',
        '.deployed-tags',
    ):
        assert any(fnmatch(name, pattern) or fnmatch(Path(name).name, pattern) for pattern in patterns), (
            f'{name} matches no .dockerignore pattern, so it would be copied into the image'
        )


def test_the_image_installs_a_virtual_display():
    """The live test proves it is in the built image; this one is in the gate.

    A dependency nothing imports is easy to drop, and the guard against dropping it was
    behind `live`, which nobody runs on a Tuesday.
    """
    assert 'xvfb' in (REPO / 'Dockerfile').read_text(encoding='utf-8')


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


def test_the_project_is_named_so_the_volume_does_not_depend_on_the_directory():
    """Without this, compose names the project after the working directory and prefixes
    every volume with it. The same `make up` from a worktree and from the real checkout
    would then be two different stores, both healthy, neither saying so."""
    compose = yaml.safe_load(COMPOSE.read_text(encoding='utf-8'))

    assert compose.get('name') == 'harry'


def test_the_real_stack_names_a_version_and_dev_tracks_latest():
    """Pinned to `latest`, the real stack runs whatever was built last — including a build
    somebody made to try something. `make deploy` sets HARRY_TAG; the fallback is only
    there so a machine that has never deployed can still start."""
    compose = yaml.safe_load(COMPOSE.read_text(encoding='utf-8'))

    assert compose['services']['harry']['image'] == 'harry:${HARRY_TAG:-latest}'
    assert compose['services']['harry-dev']['image'] == 'harry:latest'


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


@pytest.mark.live
def test_a_virtual_display_is_in_the_image_before_anything_needs_one(built_image):
    """De Tijd's edge refuses every headless browser, and a NUC has no screen for a headed
    one. Putting `xvfb` in now costs a few megabytes and means the feature that needs it is
    a code change rather than an image rebuild and a re-deploy.

    Nothing uses it yet. That is the point of the test: it is easy to drop a dependency
    that nothing imports, and the next person would not find out until a build they were
    hoping to avoid.
    """
    assert in_the_image('command -v Xvfb || true').strip(), 'Xvfb is not in the image'


@pytest.fixture
def running_stack():
    """The real stack, up. Skips unless it is — nothing here starts or stops it.

    `make up` is a deliberate act with a data volume behind it, so a test does not do it
    on somebody's behalf.
    """
    if shutil.which('docker') is None:
        pytest.skip('docker is not installed here')
    up = subprocess.run(
        ['docker', 'compose', 'ps', '--status', 'running', '--format', '{{.Service}}'],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    if 'harry' not in up.stdout.split():
        pytest.skip('the real stack is not running — `make up` first')

    def run(*command: str, stdin: str | None = None) -> str:
        done = subprocess.run(
            ['docker', 'compose', 'exec', '-T', 'harry', *command],
            cwd=REPO,
            input=stdin,
            capture_output=True,
            text=True,
            timeout=600,
        )
        assert done.returncode == 0, done.stderr[-2000:]
        return done.stdout

    return run


@pytest.mark.live
def test_a_page_is_built_inside_the_container_and_stays_on_the_volume(running_stack):
    """The whole product minus the clock, on the machine that will run it.

    Reaches the real feeds and the real forecast, which is why it is `live`. It needs no
    credential: weather and news carry defaults, so this is the page a fresh NUC can build
    before anything has been configured — a weather panel and headlines and no agenda.

    `scripts/call_tool.py`, not `make`: the image has no `make` and the `Makefile` is not
    copied into it. This was a manual run recorded on the board; a note is not a control,
    and the artefact it described was deleted with the volume it lived on.
    """
    candidates = json.loads(running_stack('uv', 'run', 'python', 'scripts/call_tool.py', 'digest_list_candidates'))

    assert candidates['weather']['available'] is True, candidates['weather']
    assert candidates['agenda']['available'] is False, 'no calendar is configured, so the agenda must say so'
    assert candidates['agenda']['why'], 'the agenda is unavailable without saying why'
    assert len(candidates['headlines']) >= 10, f'only {len(candidates["headlines"])} headlines came back'

    picks = {
        'intro': 'Built by the suite, from the feeds, with nothing configured.',
        'deliver': False,
        'picks': [{'id': candidates['headlines'][0]['id'], 'note': 'The first one, unchosen.', 'topic': 'world'}],
        'more': [],
    }
    running_stack('sh', '-c', 'cat > /data/suite-picks.json', stdin=json.dumps(picks))
    answer = json.loads(
        running_stack(
            'uv', 'run', 'python', 'scripts/call_tool.py', 'digest_build', '--args', '@/data/suite-picks.json'
        )
    )

    assert answer['delivered']['pushed'] is False, 'deliver=false still pushed to the tablet'
    assert answer['page']['path'].startswith('/data/'), f'the page landed at {answer["page"]["path"]}, off the volume'
    assert running_stack('sh', '-c', f'test -s {answer["page"]["path"]} && echo yes').strip() == 'yes'
    assert answer['page']['pages'] >= 2, answer['page']
