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


def is_bind(volume: str | dict) -> bool:
    """A host path mounted in, as opposed to a named volume compose manages."""
    if isinstance(volume, dict):
        return volume.get('type') == 'bind'
    return volume.split(':')[0].startswith(('.', '/', '~'))


def sources(service: dict) -> set[str]:
    """The named volumes a service mounts. Empty is a finding, not a pass."""
    return {
        (volume.split(':')[0] if isinstance(volume, str) else volume.get('source', ''))
        for volume in service.get('volumes') or []
        if not is_bind(volume)
    }


def binds(service: dict) -> list[dict]:
    """Every host path a service mounts, in the long form whichever way it was written."""
    found = []
    for volume in service.get('volumes') or []:
        if not is_bind(volume):
            continue
        if isinstance(volume, dict):
            found.append(volume)
        else:
            source, target, *mode = volume.split(':')
            found.append({'source': source, 'target': target, 'read_only': mode == ['ro']})
    return found


def test_each_stack_keeps_its_data_on_a_named_volume_of_its_own():
    """The data lives on a volume, which is what makes it outlive the container.

    Narrowed from "every mount is a named volume" when the real stack began mounting the
    checkout's `.harry/` to read each connector's own `.env.local`. What this guards is
    unchanged — the store has a volume of its own on each stack — and the one bind mount is
    held to its own test below, so nothing else can arrive beside it unnoticed.

    **Every assertion here is positive first.** An earlier version compared the two
    services' mount lists for inequality, which passes when one of them mounts nothing at
    all — deleting the real stack's whole `volumes:` block left the suite green, and the
    store, every rendered page and the De Tijd session would have died with the container.
    """
    compose = yaml.safe_load(COMPOSE.read_text(encoding='utf-8'))
    # The browser container mounts nothing at all, which is its own test below.
    mounted = {name: sources(compose['services'][name]) for name in HARRY_STACKS}

    for name, found in mounted.items():
        assert found, f'{name} mounts no named volume, so everything it writes dies with the container'
        assert found <= set(compose['volumes']), f'{name} mounts {found - set(compose["volumes"])}, not a named volume'

    assert not (mounted['harry'] & mounted['harry-dev']), (
        f'both stacks mount {mounted["harry"] & mounted["harry-dev"]} — `down -v` on dev would take the real store'
    )


def test_the_real_stack_reads_connector_settings_through_one_read_only_mount_and_dev_through_none():
    """Where every connector's `.env.local` reaches the real stack, and where it must not reach.

    - **Read-only.** The container reads credentials; it has no business writing next to them.
    - **Only `./.harry`.** A second bind mount is how `~/.claude` or a root `.env.local` would
      arrive, and this is the test that would say so.
    - **Named by the setting.** A mount at one path and a setting naming another reads nothing,
      and every capability quietly reports its credential missing.
    - **Not on dev.** Every `.env.local` under `.harry/` is the real one — the tablet token with
      no read-only mode among them.
    """
    compose = yaml.safe_load(COMPOSE.read_text(encoding='utf-8'))
    real, dev = compose['services']['harry'], compose['services']['harry-dev']

    mounts = binds(real)
    assert len(mounts) == 1, f'the real stack mounts {mounts}; only ./.harry belongs here'
    (settings,) = mounts
    assert settings['source'] == './.harry', settings
    assert settings.get('read_only') is True, 'the checkout holding every credential is mounted writable'
    assert real['environment'].get('HARRY_CAPABILITY_SETTINGS_DIR') == settings['target'], (
        'HARRY_CAPABILITY_SETTINGS_DIR does not name where .harry/ is mounted, so no credential is read from it'
    )

    assert binds(dev) == [], f'the dev stack mounts {binds(dev)} — it would read the real credentials'
    assert 'HARRY_CAPABILITY_SETTINGS_DIR' not in (dev.get('environment') or {})


def test_the_two_stacks_cannot_collide_on_a_port_a_name_or_a_volume():
    """The promise this module's docstring makes, asserted rather than described.

    Each of these was checked only against itself before: every service agreed with its own
    published port, and nothing noticed when both services published 7430 under the same
    container name.
    """
    compose = yaml.safe_load(COMPOSE.read_text(encoding='utf-8'))
    services = {name: compose['services'][name] for name in HARRY_STACKS}

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

    # The browser container reads no env file at all, which is its own test.
    for name in HARRY_STACKS:
        service = compose['services'][name]
        paths = [entry if isinstance(entry, str) else entry['path'] for entry in service['env_file']]
        assert paths[0] == '.env', f'{name} reads {paths[0]} before the committed defaults'
        assert len(paths) == 2, f'{name} reads {paths}, and only two files have a defined precedence'


def excluded_by(pattern: str, path: str) -> bool:
    """Docker's `.dockerignore` matching, modelled segment by segment.

    Three things make it unlike `fnmatch` on the whole string, and the middle one is the
    reason this function exists rather than a one-liner:

    - patterns are rooted at the build context, so they are matched from the left
    - **`*` does not cross a `/`, and a bare name does not match a nested one.** Measured:
      a context whose `.dockerignore` holds only `.env.local` excludes the root file and
      copies `sub/.env.local` straight in
    - `**` matches any number of segments, including none

    An earlier version of this test also matched each pattern against the path's basename,
    which Docker never does — so `**/.env.local` could be deleted and this still passed,
    while five real `.env.local` files sit in `.harry/` on the machine that builds.
    """
    want, got = pattern.split('/'), path.split('/')

    def walk(w: list[str], g: list[str]) -> bool:
        if not w:
            return not g
        if w[0] == '**':
            return any(walk(w[1:], g[i:]) for i in range(len(g) + 1))
        return bool(g) and fnmatch(g[0], w[0]) and walk(w[1:], g[1:])

    return walk(want, got)


def dockerignore() -> list[str]:
    return [
        line.strip()
        for line in (REPO / '.dockerignore').read_text(encoding='utf-8').splitlines()
        if line.strip() and not line.startswith('#')
    ]


def test_the_matcher_this_file_checks_dockerignore_with_is_the_one_docker_uses():
    """The model is under test before anything is tested with it.

    Every case below was checked against a real `docker build` rather than reasoned about.
    Without this, a matcher that said yes to everything would make the test beneath it
    pass while proving nothing.
    """
    assert excluded_by('.env.local', '.env.local')
    assert not excluded_by('.env.local', 'sub/.env.local'), 'a bare name must not match a nested file'
    assert excluded_by('**/.env.local', 'sub/deeper/.env.local')
    assert excluded_by('**/.env.local', '.env.local'), '`**` matches no segments too'
    assert excluded_by('.env.*.local', '.env.dev.local')
    assert not excluded_by('.env.*.local', 'sub/.env.dev.local')
    assert not excluded_by('*.local', 'sub/x.local'), '`*` does not cross a slash'


def test_every_credential_path_on_this_machine_is_excluded_from_the_image():
    """The five nested `.env.local` files in `.harry/` are real, and one of them holds a
    token that can rewrite every document on the tablet.

    `make deploy` builds from the primary checkout, which has them. `**/.env.local` is what
    keeps them out — not `.env.local`, which only covers the one at the root.
    """
    patterns = dockerignore()

    for name in (
        '.env.local',
        '.env.dev.local',
        '.harry/connectors/remarkable/.env.local',
        '.harry/connectors/icloud/.env.local',
        '.harry/connectors/slack/.env.dev.local',
        '.harry/tools/digest_build/.env.local',
        'storage-state.json',
        '.deployed-tags',
    ):
        assert any(excluded_by(pattern, name) for pattern in patterns), (
            f'{name} matches no .dockerignore pattern, so it would be copied into the image'
        )


def test_the_image_installs_a_virtual_display():
    """The live test proves it is in the built image; this one is in the gate.

    A dependency nothing imports is easy to drop, and the guard against dropping it was
    behind `live`, which nobody runs on a Tuesday.

    The install line, not the word: `'xvfb' in dockerfile` passes when the `apt-get` line
    is gone and only the comment explaining it survives — which is exactly the shape of
    "dropping xvfb, nothing uses it".
    """
    # Continuations joined first, so a package on its own indented line is part of the
    # install it belongs to rather than a line of its own.
    dockerfile = (REPO / 'Dockerfile').read_text(encoding='utf-8').replace('\\\n', ' ')
    installs = ' '.join(re.findall(r'apt-get install[^\n]*', dockerfile)).split()

    assert 'xvfb' in installs, 'xvfb is mentioned but never installed'
    # `xvfb-run` refuses to start without it. With `xvfb` alone the image passed this test
    # and a headed browser still could not be launched the way anyone would launch one.
    assert 'xauth' in installs, 'xvfb is installed without xauth, so `xvfb-run` fails on its first call'


def test_the_image_starts_the_display_before_harry_and_hands_harry_the_signals():
    """The display De Tijd's browser draws on is the image's, started by its entrypoint.

    Four things, each the way it breaks:

    - **No entrypoint, or no `DISPLAY`.** Harry starts healthy and every De Tijd article answers
      "the browser could not start", which is a real alert about a missing line here.
    - **Xvfb in the foreground.** The shell waits on it forever and Harry never starts.
    - **No `exec`.** The shell stays PID 1 and swallows `docker stop`, so every stop and every
      deploy waits out Docker's ten seconds and kills Harry mid-write.
    - **No stale-lock removal.** A container restarted in place keeps `/tmp`, and Xvfb refuses
      the display its last run locked.
    """
    dockerfile = (REPO / 'Dockerfile').read_text(encoding='utf-8')
    entrypoint = re.search(r'^ENTRYPOINT\s+(\[.*\])\s*$', dockerfile, re.MULTILINE)
    assert entrypoint, 'the image has no entrypoint, so nothing starts a display'
    assert json.loads(entrypoint.group(1)) == ['/app/scripts/with-display.sh']
    assert re.search(r'^ENV DISPLAY=:\d+\s*$', dockerfile, re.MULTILINE), 'DISPLAY is not set in the image'

    script = REPO / 'scripts' / 'with-display.sh'
    assert script.stat().st_mode & 0o111, 'the entrypoint is not executable, so the container cannot start'
    lines = [line.strip() for line in script.read_text(encoding='utf-8').splitlines()]
    code = [line for line in lines if line and not line.startswith('#')]
    started = next((index for index, line in enumerate(code) if line.startswith('Xvfb "$DISPLAY"')), None)
    assert started is not None, 'nothing starts Xvfb on $DISPLAY'
    assert code[started].endswith('&'), 'Xvfb runs in the foreground, so Harry never starts'
    assert any(line.startswith('rm -f') and '-lock' in line for line in code[:started]), 'a stale lock would stop Xvfb'
    assert code[-1] == 'exec "$@"', 'the shell stays PID 1 and swallows docker stop'
    assert any('>&2' in line and 'did not start' in line for line in code), 'a display that never came says nothing'


BROWSER = 'harry-browser'
"""The one container here that renders a commercial news site's scripts."""

HARRY_STACKS = ('harry', 'harry-dev')


def test_every_service_in_the_compose_file_is_one_of_the_three_this_suite_knows():
    """Two Harry stacks and a browser. Every test here either walks `HARRY_STACKS` or names the
    browser, so a fourth service would otherwise be checked by nothing at all."""
    compose = yaml.safe_load(COMPOSE.read_text(encoding='utf-8'))

    assert set(compose['services']) == {*HARRY_STACKS, BROWSER}


def test_the_browser_container_is_given_nothing_to_steal():
    """It meets hostile input — De Tijd's pages and the advertising on them — so what it holds is
    the whole question. No `.harry/` mount, no root `.env.local`, no data volume, no credential in
    its environment. An exploited renderer must land somewhere empty."""
    compose = yaml.safe_load(COMPOSE.read_text(encoding='utf-8'))
    browser = compose['services'][BROWSER]

    assert not browser.get('volumes'), f'the browser container mounts {browser.get("volumes")}'
    assert not browser.get('env_file'), f'the browser container reads {browser.get("env_file")}'
    assert not browser.get('ports'), 'the browser container publishes a port'
    handed = browser.get('environment') or {}
    # A clock, and two paths that keep its scratch on the tmpfs. Nothing Harry reads as a setting.
    assert set(handed) <= {'TZ', 'HOME', 'UV_CACHE_DIR'}, f'the browser container is handed {sorted(handed)}'
    assert not [key for key in handed if key.startswith('HARRY_')], f'the browser container is configured: {handed}'


def test_only_the_browser_container_has_its_syscall_filtering_relaxed():
    """Chromium's sandbox will not start under Docker's default seccomp — measured. That
    relaxation is only safe where there is nothing to take, so it belongs to the empty container
    and to no other. A stack that gained it would be running every credential under it."""
    compose = yaml.safe_load(COMPOSE.read_text(encoding='utf-8'))

    assert 'seccomp:unconfined' in (compose['services'][BROWSER].get('security_opt') or [])
    for name in HARRY_STACKS:
        assert not compose['services'][name].get('security_opt'), f'{name} relaxes its syscall filtering'
        assert not compose['services'][name].get('privileged'), f'{name} runs privileged'


def test_the_browser_container_cannot_keep_what_a_renderer_leaves():
    """Relaxed syscall filtering widens what an escape could try next, so the cheap half is taken
    back: nothing here may gain privileges, the filesystem is a tmpfs that dies with the
    container, and a fork bomb in a renderer stops at a limit."""
    compose = yaml.safe_load(COMPOSE.read_text(encoding='utf-8'))
    browser = compose['services'][BROWSER]

    assert 'no-new-privileges:true' in (browser.get('security_opt') or [])
    assert browser.get('read_only') is True, 'the browser container can write its own filesystem'
    assert set(browser.get('tmpfs') or []) >= {'/tmp'}, 'a read-only browser needs somewhere to work'
    assert browser.get('pids_limit'), 'nothing caps the processes a renderer can fork'


def test_the_browser_container_answers_a_healthcheck_of_its_own():
    """The image's asks Harry's port for /health, and nothing in this container answers that. A
    container that is permanently unhealthy is one whose health nobody reads — and `make up`
    waits on every service it starts."""
    compose = yaml.safe_load(COMPOSE.read_text(encoding='utf-8'))
    check = compose['services'][BROWSER].get('healthcheck') or {}

    assert check, 'the browser container inherits a healthcheck it can never pass'
    assert check.get('disable') is True or '3000' in ' '.join(check.get('test') or []), check


def test_the_browser_container_is_unprivileged():
    compose = yaml.safe_load(COMPOSE.read_text(encoding='utf-8'))
    browser = compose['services'][BROWSER]

    assert browser.get('user') == '1000:1000', 'the browser runs as root'
    assert browser.get('cap_drop') == ['ALL'], 'the browser keeps Linux capabilities it never needs'


def test_the_real_stack_reads_de_tijd_through_the_browser_container():
    """A stack pointed at no browser would start one inside itself, beside the credentials —
    which is the arrangement this feature exists to end."""
    compose = yaml.safe_load(COMPOSE.read_text(encoding='utf-8'))
    real = compose['services']['harry']

    assert real['environment'].get('HARRY_TIJD_BROWSER_ENDPOINT') == f'ws://{BROWSER}:3000/'
    assert BROWSER in (real.get('depends_on') or []), 'nothing starts the browser before Harry'
    assert 'HARRY_TIJD_BROWSER_ENDPOINT' not in (compose['services']['harry-dev'].get('environment') or {}), (
        'the dev stack has no De Tijd credentials, so it never opens a browser'
    )


def test_the_image_installs_its_browsers_where_an_unprivileged_user_can_read_them():
    """In root's cache, which is where they land by default, the browser container cannot open
    them: it runs as uid 1000. The failure is a browser that will not start, every article."""
    dockerfile = (REPO / 'Dockerfile').read_text(encoding='utf-8')

    assert re.search(r'^ENV PLAYWRIGHT_BROWSERS_PATH=\S+', dockerfile, re.MULTILINE), "browsers stay in root's cache"
    installs = ' '.join(re.findall(r'playwright install[^\n]*', dockerfile))
    assert 'chmod -R a+rX' in dockerfile, 'the browsers are installed but left unreadable'
    assert 'chromium' in installs


def test_both_stacks_run_an_init_that_reaps_what_a_crashed_browser_leaves():
    """After `exec`, PID 1 is `uv`, which reaps nothing. Every Chromium that crashes in a container
    that runs for months would leave its processes behind."""
    compose = yaml.safe_load(COMPOSE.read_text(encoding='utf-8'))
    for name, service in compose['services'].items():
        assert service.get('init') is True, f'{name} has no init, so orphaned browser processes are never reaped'


def test_each_stack_pins_its_own_port_and_data_directory_on_the_service():
    """`environment:` outranks `env_file:`, and that is what makes the published port true.

    Left to a file, a stray `HARRY_PORT` moves the port Harry listens on while compose
    still publishes the old one — and the healthcheck reads the same variable, so the
    container reports healthy while nothing can reach it.
    """
    compose = yaml.safe_load(COMPOSE.read_text(encoding='utf-8'))

    for name in HARRY_STACKS:
        service = compose['services'][name]
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
        for name, service in ((name, compose['services'][name]) for name in HARRY_STACKS)
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
def test_a_headed_browser_starts_in_the_image_before_anything_needs_one(built_image):
    """De Tijd's edge refuses every headless browser, and a NUC has no screen for a headed one.

    Measured from this image on 2026-09-16 against De Tijd's public homepage:
    chrome-headless-shell 403, full Chromium headless 403, headed Chromium under Xvfb 200.

    **A browser actually starting, not a binary being present.** The first version of this
    test asserted `command -v Xvfb` and passed while `xvfb-run` failed with "xauth command
    not found" — so the criterion "the De Tijd feature does not have to rebuild the image"
    was ticked and false. This launches a headed browser the conventional way and loads a
    page that needs no network, so it answers about the display and nothing else.
    """
    probe = (
        'from playwright.sync_api import sync_playwright\n'
        'with sync_playwright() as p:\n'
        "    b = p.chromium.launch(headless=False, channel='chromium')\n"
        '    page = b.new_page()\n'
        "    page.goto('data:text/html,<title>display</title>')\n"
        '    print(page.title())\n'
        '    b.close()\n'
    )
    started = in_the_image(f'xvfb-run -a uv run python -c "{probe}"')

    assert started.strip().splitlines()[-1] == 'display', started


@pytest.mark.live
def test_in_the_image_a_connector_loads_from_a_mounted_settings_directory(built_image, tmp_path):
    """The route every credential takes on the NUC, run in the image rather than described.

    A `.harry`-shaped directory holding only Slack's `.env.local` is mounted read-only, the
    way compose mounts the checkout. The same container, the same mount, one environment
    variable apart: loaded with it, skipped without. Slack because its `register` makes no
    network call, so fake values prove the settings route and nothing else.
    """
    folder = tmp_path / 'settings' / 'connectors' / 'slack'
    folder.mkdir(parents=True)
    (folder / '.env.local').write_text('BOT_TOKEN=not-a-real-token\nCHANNEL=#a-test-channel\n', encoding='utf-8')
    probe = "from harry.loader import load; found = load().get('connector', 'slack'); print(found.status)"

    def slack_status(*docker_args: str) -> str:
        ran = subprocess.run(
            ['docker', 'run', '--rm', '--entrypoint', 'sh', *docker_args, IMAGE, '-c', f'uv run python -c "{probe}"'],
            capture_output=True,
            text=True,
            timeout=120,
            check=True,
        )
        return ran.stdout.strip().splitlines()[-1]

    mount = ['-v', f'{tmp_path / "settings"}:/settings:ro']
    assert slack_status(*mount, '-e', 'HARRY_CAPABILITY_SETTINGS_DIR=/settings') == 'loaded'
    assert slack_status(*mount) == 'skipped'


@pytest.mark.live
def test_in_the_image_a_headed_browser_starts_on_the_entrypoint_s_display(built_image):
    """No `xvfb-run` here: the display has to be the one the image starts by itself.

    And PID 1 has to be the command rather than the entrypoint's shell, which is what `exec`
    buys — measured by asking PID 1 what it is.
    """
    probe = (
        'from playwright.sync_api import sync_playwright\n'
        'with sync_playwright() as p:\n'
        "    b = p.chromium.launch(headless=False, channel='chromium')\n"
        '    page = b.new_page()\n'
        "    page.goto('data:text/html,<title>display</title>')\n"
        '    print(page.title())\n'
        '    b.close()\n'
    )
    started = subprocess.run(
        ['docker', 'run', '--rm', IMAGE, 'uv', 'run', 'python', '-c', probe],
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert started.returncode == 0, started.stderr[-2000:]
    assert started.stdout.strip().splitlines()[-1] == 'display'

    first = subprocess.run(
        ['docker', 'run', '--rm', IMAGE, 'cat', '/proc/1/cmdline'], capture_output=True, text=True, timeout=60
    )
    assert first.stdout.replace('\0', ' ').strip() == 'cat /proc/1/cmdline', 'the entrypoint shell is still PID 1'


@pytest.fixture
def running_stack():
    """The real stack, up and running the code in this tree. Skips otherwise.

    Two skips rather than one. `make up` is a deliberate act with a data volume behind it,
    so nothing here starts the stack. And a container left on an older deployed tag — which
    this feature makes an ordinary state, because `make rollback` exists — would answer
    about code that is not in this tree, so the test says so instead of reporting on it.
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

    # And running THIS tree. `make rollback` exists, so a container on an older tag is an
    # ordinary state here rather than a mistake — and a live test that reported on it would
    # be answering about code nobody has in front of them. `built_image` says the same
    # thing about a stale image; this is the running half of it.
    running = subprocess.run(
        ['docker', 'inspect', 'harry', '--format', '{{.Config.Image}}'], capture_output=True, text=True
    ).stdout.strip()
    head = subprocess.run(
        ['git', 'rev-parse', '--short', 'HEAD'], cwd=REPO, capture_output=True, text=True
    ).stdout.strip()
    tag = running.partition(':')[2]
    if tag not in ('latest', '', head):
        pytest.skip(f'the stack is on {running} and this tree is {head} — `make deploy` or `make up` first')

    def run(*command: str, stdin: str | None = None, env: dict[str, str] | None = None) -> str:
        passed = [arg for key, value in (env or {}).items() for arg in ('-e', f'{key}={value}')]
        done = subprocess.run(
            ['docker', 'compose', 'exec', '-T', *passed, 'harry', *command],
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
    copied into it.

    **It writes to `/data/suite`, never `/data/digest`.** `OUT_DIR` defaults to the latter,
    which is where the real morning page lives under today's date — so an earlier version
    of this test, run on the NUC at any time after 06:30, replaced that morning's page on
    disk with one whose intro says it came from the suite. The volume is what the criterion
    is about; the folder is not.
    """
    somewhere_else = '/data/suite'
    # What the real morning page folder holds now, content and all. On the NUC that is a
    # real page under today's date, so "is it still exactly there afterwards" is the
    # question — not "is the folder empty", which is only true on a machine that has never
    # built one.
    before = running_stack('sh', '-c', 'md5sum /data/digest/* 2>/dev/null | sort || true')

    running_stack('sh', '-c', f'rm -rf {somewhere_else} && mkdir -p {somewhere_else}')
    try:
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
        running_stack('sh', '-c', f'cat > {somewhere_else}/picks.json', stdin=json.dumps(picks))
        answer = json.loads(
            running_stack(
                'uv',
                'run',
                'python',
                'scripts/call_tool.py',
                'digest_build',
                '--args',
                f'@{somewhere_else}/picks.json',
                env={'HARRY_DIGEST_BUILD_OUT_DIR': somewhere_else},
            )
        )

        assert answer['delivered']['pushed'] is False, 'deliver=false still pushed to the tablet'
        assert answer['page']['path'].startswith('/data/'), (
            f'the page landed at {answer["page"]["path"]}, off the volume'
        )
        assert answer['page']['path'].startswith(somewhere_else), (
            f'the page landed at {answer["page"]["path"]} — that is where a real morning page lives'
        )
        assert running_stack('sh', '-c', f'test -s {answer["page"]["path"]} && echo yes').strip() == 'yes'
        assert answer['page']['pages'] >= 2, answer['page']

        after = running_stack('sh', '-c', 'md5sum /data/digest/* 2>/dev/null | sort || true')
        assert after == before, 'the suite changed the folder the real morning page lives in'
    finally:
        running_stack('sh', '-c', f'rm -rf {somewhere_else}')
