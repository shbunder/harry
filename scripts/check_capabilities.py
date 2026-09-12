#!/usr/bin/env python3
"""Validate everything declared under `.harry/`.

Connectors and jobs are discovered from the filesystem, which buys a format anyone can add
to without writing Python — and costs the guarantee an import gave for free, that a broken
declaration fails loudly and immediately. This is that guarantee, moved to the gate.

Run by `make lint`. See ADR-260912-399f07 and `.claude/rules/capability-shape.md`.

    python scripts/check_capabilities.py
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import yaml

from harry.config import env_key

SUMMARY = (__doc__ or '').partition('\n')[0]

ROOT = Path(__file__).parent.parent
HARRY = ROOT / '.harry'

TRIGGERS = ('claude', 'schedule')
EXPIRIES = ('never', 'manual', 'session')
NAME_RE = re.compile(r'^[a-z][a-z0-9-]*$')
# Underscores, never dots. MCP permits dots in a tool name but the Claude API's own
# validation is narrower, and the intersection is what survives the trip — ADR-260912-b22e46.
TOOL_NAME_RE = re.compile(r'^[a-z][a-z0-9_]*$')
TIME_RE = re.compile(r'^\d{2}:\d{2}$')
CONFIG_KEY_RE = re.compile(r'^[a-z][a-z0-9_]*$')
# The four MCP behaviour hints. They are per tool, which is why a tool that does two things
# cannot carry them.
ANNOTATIONS = ('readOnlyHint', 'destructiveHint', 'idempotentHint', 'openWorldHint')
# Five fields, any of which may be `*`, a number, a range, a step or a list.
CRON_RE = re.compile(r'^\s*(\S+\s+){4}\S+\s*$')


class Problem(Exception):
    """One thing wrong with one declaration."""


def read_frontmatter(path: Path) -> dict[str, Any]:
    """The YAML header, or a Problem naming what is missing."""
    text = path.read_text(encoding='utf-8')
    if not text.startswith('---'):
        raise Problem('no YAML frontmatter — the file must open with `---`')
    _, _, rest = text.partition('---\n')
    block, separator, _ = rest.partition('\n---')
    if not separator:
        raise Problem('the frontmatter block is never closed with `---`')
    try:
        loaded = yaml.safe_load(block)
    except yaml.YAMLError as error:
        raise Problem(f'the frontmatter is not valid YAML: {error}') from error
    if not isinstance(loaded, dict):
        raise Problem('the frontmatter must be a mapping of key to value')
    return loaded


def read_body(path: Path) -> str:
    """Everything after the closing `---`.

    Split on `\n---` rather than `---`: the opening delimiter is at offset 0 with no
    newline before it, so the first match is always the closing one. An earlier version
    partitioned twice and returned the empty string for every well-formed file — which
    looked like every body being empty rather than like a bug.
    """
    return path.read_text(encoding='utf-8').partition('\n---')[2].strip()


def require(fields: dict[str, Any], key: str, kind: type | tuple[type, ...] = str) -> Any:
    value = fields.get(key)
    if value is None or value == '':
        raise Problem(f'`{key}` is required and is missing or empty')
    if not isinstance(value, kind):
        wanted = kind.__name__ if isinstance(kind, type) else ' or '.join(k.__name__ for k in kind)
        raise Problem(f'`{key}` must be {wanted}, got {type(value).__name__}')
    return value


def check_name(fields: dict[str, Any], directory: Path) -> None:
    name = require(fields, 'name')
    if not NAME_RE.match(name):
        raise Problem(f'`name` must be lowercase letters, digits and hyphens — got {name!r}')
    if name != directory.name:
        raise Problem(f'`name` is {name!r} but the folder is {directory.name!r}; they must match')


def check_job(path: Path, fields: dict[str, Any], connectors: set[str]) -> None:
    check_name(fields, path.parent)
    require(fields, 'description')
    require(fields, 'enabled', bool)

    trigger = require(fields, 'trigger')
    if trigger not in TRIGGERS:
        raise Problem(f'`trigger` must be one of {", ".join(TRIGGERS)} — got {trigger!r}')

    schedule = fields.get('schedule')
    if trigger == 'schedule':
        if not schedule:
            raise Problem('`trigger: schedule` needs a `schedule:` — Harry has no idea when to run it')
        if not CRON_RE.match(str(schedule)):
            raise Problem(f'`schedule` must be five cron fields — got {schedule!r}')
        if not fields.get('timezone'):
            raise Problem('`timezone` is required with a schedule — 06:30 is a local time, not a UTC one')
    elif schedule:
        raise Problem(
            '`trigger: claude` means a Claude scheduled task owns the clock, so `schedule:` here '
            'would be a second one that disagrees. Remove it, or set `trigger: schedule`.'
        )

    deadline = fields.get('deadline')
    if deadline is not None and not TIME_RE.match(str(deadline)):
        raise Problem(f'`deadline` must be HH:MM — got {deadline!r}')
    if trigger == 'claude' and deadline is None:
        raise Problem(
            'a job Harry does not trigger needs a `deadline:`, or nothing can notice it never ran. '
            'An external trigger cannot report its own absence — see ADR-260912-bd36c2.'
        )

    check_requires(fields, connectors)
    check_config(fields, str(fields['name']))


def check_connector(path: Path, fields: dict[str, Any]) -> None:
    check_name(fields, path.parent)
    require(fields, 'description')
    require(fields, 'enabled', bool)

    env = fields.get('requires_env', [])
    if not isinstance(env, list):
        raise Problem('`requires_env` must be a list, even with one entry')
    for key in env:
        if not isinstance(key, str) or not key.isupper():
            raise Problem(f'`requires_env` entries are environment variable names — got {key!r}')

    expires = fields.get('expires')
    if expires is None:
        raise Problem(
            '`expires` is required — never, manual or session. A credential nobody declared as '
            "expiring is one nobody watches, and two of Harry's three do expire."
        )
    if expires not in EXPIRIES:
        raise Problem(f'`expires` must be one of {", ".join(EXPIRIES)} — got {expires!r}')

    check_config(fields, str(fields['name']))


def check_tool(path: Path, fields: dict[str, Any], connectors: set[str]) -> None:
    name = require(fields, 'name')
    if not TOOL_NAME_RE.match(name):
        raise Problem(f'`name` must be lowercase letters, digits and underscores — got {name!r}')
    if name != path.parent.name:
        raise Problem(f'`name` is {name!r} but the folder is {path.parent.name!r}; they must match')

    namespace = require(fields, 'namespace')
    if not name.startswith(f'{namespace}_'):
        raise Problem(
            f'`name` must start with its namespace — expected {namespace}_…, got {name!r}. '
            "The prefix is how the model tells one owner's tools from another's."
        )

    require(fields, 'description')
    require(fields, 'enabled', bool)
    require(fields, 'always_load', bool)

    annotations = fields.get('annotations') or {}
    if not isinstance(annotations, dict):
        raise Problem('`annotations` must be a mapping of hint to true/false')
    for key, value in annotations.items():
        if key not in ANNOTATIONS:
            raise Problem(f'unknown annotation {key!r} — MCP defines {", ".join(ANNOTATIONS)}')
        if not isinstance(value, bool):
            raise Problem(f'annotation {key!r} must be true or false, got {value!r}')
    if 'readOnlyHint' not in annotations:
        raise Problem(
            '`annotations.readOnlyHint` is required. It is what lets a client gate a tool that '
            'reaches the tablet without gating one that reads a feed — and nothing else carries '
            'that signal.'
        )

    check_requires(fields, connectors)

    # The body is the MCP description Claude reads to decide whether to call this tool.
    # An empty one is a tool the model can only pick by name.
    check_config(fields, str(fields['name']))

    # The body is the MCP description Claude reads to decide whether to call this tool.
    if len(read_body(path)) < 40:
        raise Problem(
            'the body is the description Claude reads before calling this tool, and it is '
            'nearly empty. Say what it returns, when to reach for it, and when not to.'
        )


def check_config(fields: dict[str, Any], implementation: str) -> None:
    """A capability declares its own settings; the deployment supplies the values.

    Nothing here goes in a global namespace, so `HARRY_ARTICLE_LIMIT` — a setting exactly
    one job reads — stops being everybody's business.
    """
    config = fields.get('config') or {}
    if not isinstance(config, dict):
        raise Problem('`config` must be a mapping of setting name to its declaration')

    for name, spec in config.items():
        where = f'config.{name}'
        if not CONFIG_KEY_RE.match(str(name)):
            raise Problem(f'{where}: setting names are lowercase with underscores')
        if not isinstance(spec, dict):
            raise Problem(f'{where}: must be a mapping — give it at least a `description`')
        if not spec.get('description'):
            raise Problem(
                f'{where}: `description` is required. It becomes the comment beside '
                f'{env_key(implementation, str(name))} in the generated .env, and that file is '
                'the only place anyone finds out the setting exists.'
            )
        for flag in ('required', 'secret'):
            if flag in spec and not isinstance(spec[flag], bool):
                raise Problem(f'{where}: `{flag}` must be true or false')
        if spec.get('required') and 'default' in spec:
            raise Problem(
                f'{where}: it has a `default`, so it is not `required`. Required means Harry '
                'cannot start this capability without a value.'
            )
        if spec.get('secret') and 'default' in spec:
            raise Problem(f'{where}: a secret must not carry a default — that default is a credential')


def check_requires(fields: dict[str, Any], connectors: set[str]) -> None:
    needed = fields.get('requires', [])
    if not isinstance(needed, list):
        raise Problem('`requires` must be a list of connector names')
    missing = sorted(set(needed) - connectors)
    if missing:
        known = ', '.join(sorted(connectors)) or 'none are declared yet'
        raise Problem(f'requires connectors that do not exist: {", ".join(missing)} (known: {known})')


KINDS = (('connectors', 'CONNECTOR.md'), ('tools', 'TOOL.md'), ('jobs', 'JOB.md'))


def declarations(kind: str, filename: str) -> list[Path]:
    directory = HARRY / kind
    return sorted(directory.glob(f'*/{filename}')) if directory.is_dir() else []


def validate(paths: list[Path], check, *args: Any) -> tuple[list[str], list[dict[str, Any]]]:
    """Run one kind's check over its declarations, collecting problems rather than stopping.

    A gate that stops at the first fault costs a round trip per fault.
    """
    problems: list[str] = []
    valid: list[dict[str, Any]] = []
    for path in paths:
        try:
            fields = read_frontmatter(path)
            check(path, fields, *args)
            valid.append(fields)
        except Problem as problem:
            problems.append(f'{path.relative_to(ROOT)}: {problem}')
    return problems, valid


def orphan_folders() -> list[str]:
    """Folders with no declaration — the failure the filesystem format adds.

    It looks present and does nothing, where an import would have raised.
    """
    found: list[str] = []
    for kind, filename in KINDS:
        directory = HARRY / kind
        for folder in sorted(directory.iterdir()) if directory.is_dir() else []:
            if folder.is_dir() and not (folder / filename).exists():
                found.append(f'{folder.relative_to(ROOT)}: no {filename}, so nothing here is loaded')
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='check_capabilities.py', description=SUMMARY)
    parser.parse_args(argv)

    connector_files = declarations('connectors', 'CONNECTOR.md')
    job_files = declarations('jobs', 'JOB.md')
    tool_files = declarations('tools', 'TOOL.md')

    # Connectors first: `requires` on a job or a tool is checked against what they declare.
    problems, valid_connectors = validate(connector_files, check_connector)
    connectors = {str(fields['name']) for fields in valid_connectors}

    job_problems, _ = validate(job_files, check_job, connectors)
    tool_problems, valid_tools = validate(tool_files, check_tool, connectors)
    problems += job_problems + tool_problems

    loaded = sum(1 for f in valid_tools if f.get('always_load') and f.get('enabled'))

    # Deferring every tool is a 400 from the API, not a slow path: the search tool needs
    # something already in the roster to sit alongside. Catching it here beats catching it
    # on the first call of the morning.
    if tool_files and not loaded and not problems:
        problems.append(
            '.harry/tools: every tool is deferred or disabled. At least one enabled tool must set '
            '`always_load: true`, or the API rejects the whole roster.'
        )

    problems += orphan_folders()

    if problems:
        print(f'{len(problems)} problem(s) in .harry:\n', file=sys.stderr)
        for problem in problems:
            print(f'  {problem}', file=sys.stderr)
        print('\nSee .claude/rules/capability-shape.md and .harry/README.md.', file=sys.stderr)
        return 1

    total = len(connector_files) + len(job_files) + len(tool_files)
    summary = (
        f'✓ {len(connector_files)} connector(s), {len(job_files)} job(s), '
        f'{len(tool_files)} tool(s) — {loaded} always loaded'
    )
    print(summary if total else '✓ .harry is empty')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
