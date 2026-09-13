"""Harry never calls a model, asserted rather than believed.

`.claude/rules/no-model-calls.md` is the rule; this file is what makes breaking it fail,
because a boundary that only exists in prose is the control
`.claude/rules/inert-controls.md` describes.

Each check is cheap and reads the real artifact — the dependency tree as resolved, the
image as it will be built, the compose file as it will be run.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent

# Clients that reach a model provider. Not an exhaustive list of every library in the
# world — an exhaustive list of the ones somebody would plausibly reach for here.
MODEL_CLIENTS = (
    'anthropic',
    'openai',
    'google-generativeai',
    'google-genai',
    'mistralai',
    'cohere',
    'ollama',
    'litellm',
    'langchain',
    'llama-index',
    'pydantic-ai',
    'transformers',
    'claude-agent-sdk',
    'claude-code-sdk',
)

PROVIDER_CREDENTIALS = ('ANTHROPIC_API_KEY', 'OPENAI_API_KEY', 'ANTHROPIC_AUTH_TOKEN')


def declared_dependencies() -> list[str]:
    """Every dependency Harry declares, normalised to a bare package name."""
    root = tomllib.loads((ROOT / 'pyproject.toml').read_text())

    raw = list(root['project'].get('dependencies', []))
    for group in root.get('dependency-groups', {}).values():
        raw += [entry for entry in group if isinstance(entry, str)]

    names = []
    for entry in raw:
        # Strip the version pin, the extras bracket and any environment marker, so
        # entries shaped like fastapi>=0.115 and coverage[toml]>=7.6 both reduce to a
        # bare name.
        name = entry.split(';')[0].strip()
        for separator in ('>=', '<=', '==', '!=', '~=', '>', '<', '['):
            name = name.split(separator)[0]
        names.append(name.strip().lower())
    return names


def test_harry_declares_no_model_client():
    declared = declared_dependencies()
    found = [name for name in declared if name in MODEL_CLIENTS]
    assert not found, (
        f'Harry declares a model client: {found}. Claude has the LLM; Harry performs '
        f'heuristic work only. See .claude/rules/no-model-calls.md.'
    )


def test_no_model_client_reaches_the_resolved_lockfile():
    """The declared list is what somebody typed. The lockfile is what actually installs.

    A model client arriving as a transitive dependency of something innocent is the case
    the declaration check cannot see, and it is the one that would go unnoticed.
    """
    lock = (ROOT / 'uv.lock').read_text()
    locked = {line.split('"')[1] for line in lock.splitlines() if line.startswith('name = "')}
    found = sorted(locked & set(MODEL_CLIENTS))
    assert not found, f'a model client is in the resolved dependency tree: {found}'


def test_config_declares_no_provider_credential():
    source = (ROOT / 'src' / 'harry' / 'config.py').read_text()
    for credential in PROVIDER_CREDENTIALS:
        assert credential not in source, f'{credential} is declared in config.py. Harry holds no provider credential.'


def test_no_source_file_shells_out_to_a_model_cli():
    """Shelling out to the CLI is how a model gets back inside Harry by the side door."""
    offenders = []
    for path in (ROOT / 'src').rglob('*.py'):
        text = path.read_text(encoding='utf-8')
        if "'claude'" in text or '"claude"' in text or 'claude -p' in text:
            offenders.append(str(path.relative_to(ROOT)))
    assert not offenders, f'a source file invokes the Claude CLI: {offenders}'


@pytest.mark.parametrize(
    'needle, why',
    [
        ('claude-code', 'the Claude Code CLI has no place in the image'),
        ('claude-agent-sdk', 'an agent SDK in the image means Harry runs a model'),
        ('ANTHROPIC_API_KEY', 'Harry holds no provider credential'),
    ],
)
def test_the_image_installs_no_model_tooling(needle: str, why: str):
    assert needle not in (ROOT / 'Dockerfile').read_text(), f'Dockerfile: {why}'


def test_compose_mounts_nobody_s_claude_credentials():
    """Mounting `~/.claude` into the container is how a personal token gets in."""
    compose = (ROOT / 'docker-compose.yml').read_text()
    assert '/root/.claude' not in compose
    assert '.claude:ro' not in compose
