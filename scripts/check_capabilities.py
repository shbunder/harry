#!/usr/bin/env python3
"""Validate everything declared under `.harry/`.

Connectors and jobs are discovered from the filesystem, which buys a format anyone can add
to without writing Python — and costs the guarantee an import gave for free, that a broken
declaration fails loudly and immediately. This is that guarantee, moved to the gate.

Run by `make lint`. See `.claude/rules/capability-shape.md`.

    python scripts/check_capabilities.py
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from harry.config import env_key
from harry.declaration import KINDS as DECLARED_KINDS, Malformed, read_body, read_frontmatter

SUMMARY = (__doc__ or '').partition('\n')[0]

ROOT = Path(__file__).parent.parent
HARRY = ROOT / '.harry'

TRIGGERS = ('claude', 'schedule')
EXPIRIES = ('never', 'manual', 'session')
NAME_RE = re.compile(r'^[a-z][a-z0-9-]*$')
# Underscores, never dots. MCP permits dots in a tool name but the Claude API's own
# validation is narrower, and the intersection is what survives the trip.
TOOL_NAME_RE = re.compile(r'^[a-z][a-z0-9_]*$')
TIME_RE = re.compile(r'^\d{2}:\d{2}$')
CONFIG_KEY_RE = re.compile(r'^[a-z][a-z0-9_]*$')
# The four MCP behaviour hints. They are per tool, which is why a tool that does two things
# cannot carry them.
ANNOTATIONS = ('readOnlyHint', 'destructiveHint', 'idempotentHint', 'openWorldHint')
# Five fields, any of which may be `*`, a number, a range, a step or a list.
CRON_RE = re.compile(r'^\s*(\S+\s+){4}\S+\s*$')
# The tool a `trigger: claude` brief has to ask for. Harry cannot infer that a job it
# does not fire has finished, so the sentence in the brief is the whole mechanism.
MARK_DONE = 'harry_mark_done'


class Problem(Malformed):
    """One thing wrong with one declaration.

    A subclass of `Malformed` so `validate` can catch both with one name: the parse
    errors come from `harry.declaration`, which the loader reads the same files with,
    and everything below adds the rules on top of them.
    """


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
            'A trigger that lives outside Harry cannot report its own absence, and silence '
            'looks exactly like a morning you did not check.'
        )

    if trigger == 'claude' and MARK_DONE not in read_body(path):
        raise Problem(
            f'the brief must end by telling Claude to call `{MARK_DONE}("{fields["name"]}")`. '
            'Harry does not fire this job, so that sentence is the only way it can ever learn '
            'the work happened — without it the deadline above reports a miss every single day, '
            'about work that was done.'
        )

    check_connector_lists(fields, connectors)
    check_config(fields, str(fields['name']), path)


def check_connector(path: Path, fields: dict[str, Any]) -> None:
    check_name(fields, path.parent)
    require(fields, 'description')
    require(fields, 'enabled', bool)

    if 'requires_env' in fields:
        raise Problem(
            '`requires_env` is retired. Declare each setting in `config:` instead, with a '
            'description and `required: true` — that carries everything this listed and a '
            'type and a default besides, and it is what generates the .env beside this file.'
        )

    expires = fields.get('expires')
    if expires is None:
        raise Problem(
            '`expires` is required — never, manual or session. A credential nobody declared as '
            "expiring is one nobody watches, and two of Harry's three do expire."
        )
    if expires not in EXPIRIES:
        raise Problem(f'`expires` must be one of {", ".join(EXPIRIES)} — got {expires!r}')

    check_config(fields, str(fields['name']), path)


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

    check_connector_lists(fields, connectors)

    # The body is the MCP description Claude reads to decide whether to call this tool.
    # An empty one is a tool the model can only pick by name.
    check_config(fields, str(fields['name']), path)

    # The body is the MCP description Claude reads to decide whether to call this tool.
    if len(read_body(path)) < 40:
        raise Problem(
            'the body is the description Claude reads before calling this tool, and it is '
            'nearly empty. Say what it returns, when to reach for it, and when not to.'
        )


def check_config(fields: dict[str, Any], implementation: str, path: Path) -> None:
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

    # A committed `.env.local` is the failure this whole layout makes possible: the
    # gitignore covers it, but a `git add -f` or a stale checkout would not be caught by
    # anything else, and what leaks is a live credential.
    if config and (folder := path.parent) and (folder / '.env.local').is_file():
        tracked = subprocess.run(
            ['git', '-C', str(ROOT), 'ls-files', '--error-unmatch', str((folder / '.env.local').relative_to(ROOT))],
            capture_output=True,
            text=True,
            check=False,
        )
        if tracked.returncode == 0:
            raise Problem(f"{folder.relative_to(ROOT)}/.env.local is tracked by git. It holds this machine's secrets.")


def check_exposure(connectors: list[dict[str, Any]], tools: list[dict[str, Any]]) -> list[str]:
    """`provides:` is where a connector writes down what it chose to offer.

    Two halves, and the second is the one that makes it more than decoration:

    - Every name in a `provides:` must be a tool that exists. A renamed tool leaves a stale
      list otherwise, and nothing would say so.
    - **Every tool namespaced after a connector must be in that connector's `provides:`.**
      `slack_post` is namespaced `slack` and there is a connector called `slack`, so the
      slack connector has to have agreed to offer it. Without this half, exposure is a
      field nobody has to fill in, and "a tool exists because someone would ask for it"
      becomes a sentence rather than a rule.

    A tool that composes several connectors — a digest built from a tablet, a feed and a
    calendar — is namespaced after none of them and is nobody's to offer. That is why the
    rule is about the namespace rather than about `requires:`.
    """
    problems: list[str] = []
    declared = {str(tool['name']) for tool in tools}
    by_name = {str(connector['name']): connector for connector in connectors}

    for connector in connectors:
        offered = connector.get('provides') or []
        if not isinstance(offered, list):
            problems.append(f'{connector["name"]}: `provides` must be a list of tool names')
            continue
        for name in offered:
            if str(name) not in declared:
                problems.append(f'{connector["name"]}: provides {name}, which is not a tool that exists')

    for tool in tools:
        namespace = str(tool.get('namespace', ''))
        owner = by_name.get(namespace)
        if owner is not None and str(tool['name']) not in (owner.get('provides') or []):
            problems.append(
                f'{tool["name"]}: the {namespace} connector does not list it in `provides:`. '
                'Exposing a read path is a choice, and that list is where the choice is written down.'
            )

    return problems


def check_connector_lists(fields: dict[str, Any], connectors: set[str]) -> None:
    """Both lists name connectors, so both are checked the same way.

    `optional:` earns the same check as `requires:` for the opposite reason: a typo in
    `requires:` skips the capability loudly, while a typo in `optional:` is silent forever —
    the name simply never appears, and the capability degrades every morning as though the
    connector were down.
    """
    check_requires(fields, connectors)
    check_optional(fields, connectors)


def check_optional(fields: dict[str, Any], connectors: set[str]) -> None:
    named = fields.get('optional', [])
    if not isinstance(named, list):
        raise Problem('`optional` must be a list of connector names')
    missing = sorted(str(name) for name in named if str(name) not in connectors)
    if missing:
        known = ', '.join(sorted(connectors)) or 'none'
        raise Problem(f'optionally names connectors that do not exist: {", ".join(missing)} (known: {known})')
    both = sorted(set(str(name) for name in named) & set(str(name) for name in fields.get('requires', [])))
    if both:
        raise Problem(f'{", ".join(both)} is in both `requires` and `optional` — it is one or the other')


def check_requires(fields: dict[str, Any], connectors: set[str]) -> None:
    needed = fields.get('requires', [])
    if not isinstance(needed, list):
        raise Problem('`requires` must be a list of connector names')
    missing = sorted(set(needed) - connectors)
    if missing:
        known = ', '.join(sorted(connectors)) or 'none are declared yet'
        raise Problem(f'requires connectors that do not exist: {", ".join(missing)} (known: {known})')


def connector_references(paths: list[Path], connectors: set[str]) -> list[str]:
    """What connectors name under `requires:` and `optional:`, once every connector is known.

    A second pass, because the first is what builds the list of names to check against. A
    declaration the first pass already refused is not reported twice.

    **A loop is refused here, of any length.** The loader loads a connector after the ones it
    names, and a loop has no such order: the first member is handed nothing for the rest, or
    skipped if it `requires:` one. That is survivable at start-up and wrong every morning.
    """
    problems: list[str] = []
    names: dict[str, set[str]] = {}
    for path in paths:
        try:
            fields = read_frontmatter(path)
        except Malformed:
            continue
        if str(fields.get('name')) not in connectors:
            continue
        try:
            check_connector_lists(fields, connectors)
        except Problem as problem:
            problems.append(f'{path.relative_to(ROOT)}: {problem}')
            continue
        names[str(fields['name'])] = {str(name) for key in ('requires', 'optional') for name in fields.get(key) or []}
    return problems + [_say_loop(loop) for loop in loops(names)]


def loops(names: dict[str, set[str]]) -> list[list[str]]:
    """Every set of connectors that name each other, round and back, including one naming itself."""

    def reach(start: str) -> set[str]:
        seen, stack = set(), [start]
        while stack:
            for name in names.get(stack.pop(), set()):
                if name not in seen:
                    seen.add(name)
                    stack.append(name)
        return seen

    reaches = {name: reach(name) for name in names}
    found: list[list[str]] = []
    for name in sorted(names):
        if name not in reaches[name]:
            continue
        loop = sorted({name} | {other for other in reaches[name] if name in reaches.get(other, set())})
        if loop not in found:
            found.append(loop)
    return found


def _say_loop(loop: list[str]) -> str:
    if len(loop) == 1:
        return f'connector {loop[0]} names itself in `requires:` or `optional:` — take the name out'
    named = f'{", ".join(loop[:-1])} and {loop[-1]}'
    return (
        f'connectors {named} name each other in `requires:` or `optional:`, so none of them can load '
        'after the others. Decide which one needs which, and take the name out of the other list'
    )


# The format itself lives in `harry.declaration`, so the gate and the loader cannot
# disagree about where a declaration is or what it is called.
KINDS = tuple((kind.folder, kind.declaration) for kind in DECLARED_KINDS)


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
        except Malformed as problem:
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
    problems += connector_references(connector_files, connectors)

    job_problems, _ = validate(job_files, check_job, connectors)
    tool_problems, valid_tools = validate(tool_files, check_tool, connectors)
    problems += job_problems + tool_problems
    problems += check_exposure(valid_connectors, valid_tools)

    loaded = sum(1 for f in valid_tools if f.get('always_load') and f.get('enabled'))

    # There used to be a rule here refusing an all-deferred `.harry/tools/`, because an
    # empty roster is a 400 from the API rather than a slow path. That was true when it was
    # written and the only tools were these. Harry now publishes two of its own that are
    # never deferred — the tool search and the job-done report — so the roster is never
    # empty and the premise is gone.
    #
    # `tests/test_mcp.py::test_the_roster_is_never_empty_even_when_every_tool_is_deferred`
    # is what keeps that true; if core ever stops guaranteeing a loaded tool, that test goes
    # red and this rule comes back.

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
