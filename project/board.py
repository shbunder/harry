#!/usr/bin/env python3
"""Harry's board CLI.

Allocates ids, writes files from templates, and mutates them safely. It exists so the
mechanical parts of tracking work are not done by hand — hand-written ids collide, and
hand-edited checklists drift out of the shape the verifiers expect.

Conventions are authoritative in `project/CLAUDE.md`; this file implements them.
Stdlib only, deliberately: it has to run before `uv sync` has ever been called.

    python project/board.py new-feature "The morning page lands on the tablet"
    python project/board.py new-feature "Cap the article count" --track story
    python project/board.py new-story "Feed fetch" --feature FEAT-260912-a1b2c3
    python project/board.py new-adr "APScheduler over cron" --feature FEAT-260912-a1b2c3
    python project/board.py touches FEAT-260912-a1b2c3 modules/news modules/digest
    python project/board.py start FEAT-260912-a1b2c3
    python project/board.py lanes
    python project/board.py list features --status "In Progress"
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import secrets
import subprocess
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn

SUMMARY = (__doc__ or '').partition('\n')[0]

BOARD = Path(__file__).parent
ROOT = BOARD.parent

FEATURES = BOARD / 'features'
STORIES = BOARD / 'stories'
REQUIREMENTS = BOARD / 'requirements'
DECISIONS = BOARD / 'decisions'
WORKTREES = ROOT / '.claude' / 'worktrees'

ID_RE = re.compile(r'^(FEAT|STORY|ADR)-(\d{6})-([0-9a-f]{6})$')
CLARIFICATION_RE = re.compile(r'\[NEEDS CLARIFICATION:[^\]]*\]')
FEAT_IN_TEXT_RE = re.compile(r'FEAT-\d{6}-[0-9a-f]{6}')

# `Done` is deliberately absent. A feature is done when its merge commit exists on the
# main line, and the board reports that rather than storing it — see `_is_merged`.
WORK_STATUSES = ('Backlog', 'In Progress')
ADR_STATUSES = ('Proposed', 'Accepted', 'Superseded')
TRACKS = ('story', 'full')

# Three, not ten. Past three you cannot hold the collisions in your head.
WIP_CAP = 3


# ---------------------------------------------------------------------------
# Ids and slugs
# ---------------------------------------------------------------------------


def new_id(kind: str, *, today: dt.date | None = None) -> str:
    """Allocate `{KIND}-{YYMMDD}-{6 hex}`.

    The date sorts and reads; the random tail means two agents opening work in the same
    minute cannot collide.
    """
    stamp = (today or dt.date.today()).strftime('%y%m%d')
    return f'{kind}-{stamp}-{secrets.token_hex(3)}'


def slugify(text: str) -> str:
    """A filesystem-safe, url-safe slug. Accents folded, punctuation dropped."""
    folded = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode()
    slug = re.sub(r'[^a-z0-9]+', '-', folded.lower()).strip('-')
    return slug[:60] or 'untitled'


def die(message: str) -> NoReturn:
    """Exit with a message on stderr. Typed NoReturn so the checker narrows after it."""
    print(f'error: {message}', file=sys.stderr)
    raise SystemExit(1)


# ---------------------------------------------------------------------------
# Git — read-only. Everything here tolerates not being in a repo yet.
# ---------------------------------------------------------------------------


def git(*args: str) -> str:
    """Run a read-only git command, returning '' rather than raising when it fails."""
    try:
        out = subprocess.run(
            ['git', '-C', str(ROOT), *args],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ''
    return out.stdout.strip() if out.returncode == 0 else ''


def main_branch() -> str:
    """The main line's name. `main` unless this repo says otherwise."""
    head = git('symbolic-ref', '--short', 'refs/remotes/origin/HEAD')
    if head:
        return head.rpartition('/')[2]
    # `master` only when it actually exists. A fresh repo has neither branch yet, and
    # answering `master` there would send every later git call at a ref that never
    # arrives — the board would report nothing merged, forever, and look right doing it.
    if not git('rev-parse', '--verify', 'main') and git('rev-parse', '--verify', 'master'):
        return 'master'
    return 'main'


def _merged_ids() -> set[str]:
    """Every feature id that has a merge commit on the main line.

    This is the whole of "done is derived". The board never stores `Done`, so the
    failure the board cannot have is a feature whose boxes are ticked and whose status
    was never flipped.
    """
    log = git('log', '--merges', '--format=%s', main_branch())
    return set(FEAT_IN_TEXT_RE.findall(log))


def _is_merged(feature_id: str) -> bool:
    return feature_id in _merged_ids()


def _branches() -> dict[str, str]:
    """Feature id -> branch name, for every local `feat/` branch."""
    found: dict[str, str] = {}
    for line in git('branch', '--list', 'feat/*', '--format=%(refname:short)').splitlines():
        match = FEAT_IN_TEXT_RE.search(line)
        if match:
            found[match.group()] = line.strip()
    return found


def _worktrees() -> dict[str, str]:
    """Feature id -> worktree path, from git's own registry rather than the directory."""
    found: dict[str, str] = {}
    path = ''
    for line in git('worktree', 'list', '--porcelain').splitlines():
        if line.startswith('worktree '):
            path = line.removeprefix('worktree ').strip()
        elif line.startswith('branch '):
            match = FEAT_IN_TEXT_RE.search(line)
            if match and path:
                found[match.group()] = path
    return found


# ---------------------------------------------------------------------------
# Locating board items
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Item:
    """A board file and the id it carries."""

    id: str
    path: Path

    @property
    def kind(self) -> str:
        return self.id.split('-')[0]

    def read(self) -> str:
        return self.path.read_text(encoding='utf-8')

    def write(self, text: str) -> None:
        self.path.write_text(text, encoding='utf-8')


def _search_dirs(kind: str) -> list[Path]:
    return {'FEAT': [FEATURES], 'STORY': [STORIES], 'ADR': [DECISIONS]}[kind]


def find(item_id: str) -> Item:
    """Locate a board file by id, or exit with a message naming what was searched."""
    if not ID_RE.match(item_id):
        die(f'{item_id!r} is not a board id — expected e.g. FEAT-260912-a1b2c3')

    kind = item_id.split('-')[0]
    for directory in _search_dirs(kind):
        matches = sorted(directory.glob(f'{item_id}-*.md'))
        if matches:
            return Item(item_id, matches[0])

    searched = ', '.join(str(d.relative_to(ROOT)) for d in _search_dirs(kind))
    die(f'no such item: {item_id} (searched {searched})')


def requirements_path(feature_id: str) -> Path:
    """One requirements page per feature, named by id alone so it is trivially findable."""
    return REQUIREMENTS / f'{feature_id}.md'


# ---------------------------------------------------------------------------
# Frontmatter
# ---------------------------------------------------------------------------


def read_frontmatter(text: str) -> dict[str, str]:
    """Parse the leading `---` block into a flat mapping.

    Deliberately not YAML: the board's frontmatter is flat `key: value` by convention,
    and a hand-rolled reader keeps this file dependency-free.
    """
    if not text.startswith('---'):
        return {}
    _, _, rest = text.partition('---\n')
    block, _, _ = rest.partition('\n---')
    fields: dict[str, str] = {}
    for line in block.splitlines():
        key, sep, value = line.partition(':')
        if sep and not key.startswith((' ', '\t', '#')):
            fields[key.strip()] = value.strip().strip('"\'')
    return fields


def set_frontmatter(text: str, key: str, value: str) -> str:
    """Replace a frontmatter value, inserting the key if it is absent."""
    pattern = re.compile(rf'^{re.escape(key)}:.*$', re.MULTILINE)
    if pattern.search(text):
        return pattern.sub(f'{key}: {value}', text, count=1)
    return text.replace('---\n', f'---\n{key}: {value}\n', 1)


def read_list(text: str, field: str) -> list[str]:
    """Read a flat `field: [a, b]` frontmatter list."""
    raw = read_frontmatter(text).get(field, '').strip()
    inner = raw.removeprefix('[').removesuffix(']').strip()
    return [part.strip() for part in inner.split(',') if part.strip()]


def _register(feature: Item, field: str, child_id: str) -> None:
    """Add a child id to one of the feature's machine-readable frontmatter lists.

    Takes a field name rather than being `_register_story`: in the repo this was adapted
    from, fixing the story path left the ADR path with the same bug untouched, three
    functions away and written the same way. One registrar means the next list added to
    the frontmatter cannot repeat it a third time.
    """
    text = feature.read()
    ids = read_list(text, field)
    if child_id in ids:
        return
    feature.write(set_frontmatter(text, field, f'[{", ".join([*ids, child_id])}]'))


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------


def feature_template(item_id: str, name: str, track: str) -> str:
    req = f'\n- Requirements: [[{item_id}]]' if track == 'full' else ''
    return f"""---
id: {item_id}
title: {name}
status: Backlog
track: {track}
created: {dt.date.today():%Y-%m-%d}
touches: []
stories: []
decisions: []
---

# {item_id} — {name}

## Summary

<!-- One paragraph: what this makes possible, in the user's terms. -->

## Acceptance criteria

<!-- One box per scenario. These are what the pre-close-verifier builds its
     traceability matrix from. -->

- [ ] <criterion>

## Stories

<!-- Maintained by `board.py new-story`. -->

## Notes

<!-- Appended by `board.py note`. -->

## Links
{req}
"""


def requirements_template(item_id: str, name: str) -> str:
    """The light page. Seven sections, and every one of them is read by somebody.

    The repo this was adapted from averaged 222 lines a page and wrote the same
    acceptance surface four times over: Gherkin scenarios, then numbered requirements
    that cited the scenarios back, then criteria on the feature, then criteria on each
    story. Numbers that matter now live on the scenario line that needs them.
    """
    return f"""---
id: {item_id}
title: {name}
---

# Requirements — {item_id} {name}

## Context & problem

<!-- The problem, in your own words. Not the solution. Someone who was not in the
     conversation should feel the pressure that makes this worth building. -->

## Goals

-

## Non-goals

<!-- What this deliberately does not do. Read at close to catch scope drift. -->

-

## Scenarios

<!-- Gherkin. Each one must be testable — it becomes an acceptance criterion and then
     a test. Put the numbers here, on the line that needs them: a limit, a timeout, a
     page size, a path. There is no separate requirements list to restate them in. -->

### Scenario 1: <name>

```gherkin
Given <the starting state>
When <the action>
Then <the observable outcome>
```

## When it degrades

<!-- Harry talks to things that break: a bot-blocked news site, an expired browser
     session, a reverse-engineered tablet API. Say what this does when its source is
     gone — what still renders, and what reaches you. See
     .claude/rules/external-sources.md. Write "nothing external" if it touches none. -->

## Out of scope

-

## Open questions

<!-- Where an answer changes the design, mark it inline in the section it affects:
         [NEEDS CLARIFICATION: <the question>]
     The feature cannot leave Backlog while one is live.

     Once answered: fold the answer into the scenario it changed and delete the
     marker. There is no transcript section — a resolved debate left on the page is
     noise the next agent will dutifully act on. -->

-

## Links

-
"""


def story_template(item_id: str, name: str, feature_id: str) -> str:
    return f"""---
id: {item_id}
title: {name}
feature: {feature_id}
status: Backlog
created: {dt.date.today():%Y-%m-%d}
---

# {item_id} — {name}

Part of [[{feature_id}]].

## Description

<!-- What changes, and why this is one unit of work rather than two. -->

## Acceptance criteria

<!-- These drive the tests. Write checkable statements, not activities.
     Bad:  Wire up the article fetcher
     Good: A De Tijd article whose browser session has expired falls back to its RSS
           summary, and the page still renders -->

- [ ] <criterion>

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

"""


def adr_template(item_id: str, title: str, feature_id: str | None) -> str:
    link = f'\n\nDrives [[{feature_id}]].' if feature_id else ''
    return f"""---
id: {item_id}
title: {title}
status: Proposed
created: {dt.date.today():%Y-%m-%d}
feature: {feature_id or ''}
supersedes: ''
superseded_by: ''
---

# {item_id} — {title}

## Status

Proposed{link}

## Context & problem

<!-- What forces the decision. Written so someone who was not here can feel it. -->

## Decision drivers

-

## Considered options

<!-- At least two, genuinely. The rejected option gets a fair statement of its case —
     an ADR whose alternatives are strawmen is a rationalisation with a template
     around it. -->

### Option 1: <name>

**For:**
**Against:**

### Option 2: <name>

**For:**
**Against:**

## Decision outcome

<!-- Active voice: "Claude has the LLM; Harry performs heuristic work only."
     Not "It was decided that...". Name the core principle that drove it, if one
     did — Heuristic, Modular, Degrading, Alerting, Bounded, Explainable. -->

## Consequences

<!-- The good and the bad. Name what this makes HARDER. That paragraph is the one
     people come back for. -->

**Good:**

**Bad:**
"""


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def cmd_new_feature(args: argparse.Namespace) -> int:
    feature_id = new_id('FEAT')
    slug = slugify(args.name)

    feature_file = FEATURES / f'{feature_id}-{slug}.md'
    feature_file.write_text(feature_template(feature_id, args.name, args.track), encoding='utf-8')

    print(feature_id)
    print(f'  track:        {args.track}')
    print(f'  feature:      {feature_file.relative_to(ROOT)}')

    if args.track == 'full':
        req_file = requirements_path(feature_id)
        req_file.write_text(requirements_template(feature_id, args.name), encoding='utf-8')
        print(f'  requirements: {req_file.relative_to(ROOT)}')
    else:
        print('  requirements: none — the story track carries its criteria on the feature')

    if args.touches:
        _write_touches(Item(feature_id, feature_file), args.touches)
        print(f'  touches:      {", ".join(args.touches)}')

    print(f'  branch:       feat/{feature_id}-{slug}')
    return 0


def cmd_new_story(args: argparse.Namespace) -> int:
    feature = find(args.feature)
    if feature.kind != 'FEAT':
        die(f'--feature must be a FEAT id, got {args.feature}')

    story_id = new_id('STORY')
    slug = slugify(args.name)
    story_file = STORIES / f'{story_id}-{slug}.md'
    story_file.write_text(story_template(story_id, args.name, feature.id), encoding='utf-8')

    _append_to_section(feature, 'Stories', f'- [ ] [[{story_id}]] — {args.name}')
    _register(feature, 'stories', story_id)

    print(story_id)
    print(f'  story: {story_file.relative_to(ROOT)}')
    return 0


def cmd_new_adr(args: argparse.Namespace) -> int:
    feature_id = find(args.feature).id if args.feature else None

    adr_id = new_id('ADR')
    slug = slugify(args.title)
    adr_file = DECISIONS / f'{adr_id}-{slug}.md'
    adr_file.write_text(adr_template(adr_id, args.title, feature_id), encoding='utf-8')

    if feature_id:
        _append_to_section(find(feature_id), 'Links', f'- Decision: [[{adr_id}]] — {args.title}')
        # `find` again: `_append_to_section` has just rewritten the file, and registering
        # from a stale read would drop the link it added.
        _register(find(feature_id), 'decisions', adr_id)

    print(adr_id)
    print(f'  decision: {adr_file.relative_to(ROOT)}')
    return 0


def _write_touches(feature: Item, paths: list[str]) -> None:
    cleaned = sorted({p.strip().strip('/') for p in paths if p.strip()})
    feature.write(set_frontmatter(feature.read(), 'touches', f'[{", ".join(cleaned)}]'))


def cmd_touches(args: argparse.Namespace) -> int:
    """Declare which areas a feature will edit. The lane map is built from this."""
    feature = find(args.id)
    if feature.kind != 'FEAT':
        die('only a feature declares what it touches')
    if not args.paths:
        print(f'{feature.id}: {", ".join(read_list(feature.read(), "touches")) or "(nothing declared)"}')
        return 0
    _write_touches(feature, args.paths)
    print(f'{feature.id}: touches {", ".join(read_list(feature.read(), "touches"))}')
    return 0


def _in_progress() -> list[tuple[Item, list[str]]]:
    """Every feature marked In Progress that has not been merged, with what it touches."""
    live: list[tuple[Item, list[str]]] = []
    merged = _merged_ids()
    for path in sorted(FEATURES.glob('FEAT-*.md')):
        text = path.read_text(encoding='utf-8')
        fm = read_frontmatter(text)
        item_id = fm.get('id', '')
        if fm.get('status') == 'In Progress' and item_id not in merged:
            live.append((Item(item_id, path), read_list(text, 'touches')))
    return live


def cmd_start(args: argparse.Namespace) -> int:
    """Move a feature to In Progress, refusing a collision or a broken cap.

    Three gates, in the order that fails cheapest first: live clarification markers,
    the work-in-progress cap, then an overlap with what another live feature declared.
    """
    feature = find(args.id)
    if feature.kind != 'FEAT':
        die('only a feature is started — a story follows its feature')

    live_markers = _live_clarifications(feature)
    if live_markers:
        print(f'error: {feature.id} has {len(live_markers)} live clarification marker(s):', file=sys.stderr)
        for location, marker in live_markers:
            print(f'  {location}: {marker}', file=sys.stderr)
        print('\nResolve each with a human, then fold the answer into the scenario', file=sys.stderr)
        print('it changed and delete the marker.', file=sys.stderr)
        return 1

    mine = read_list(feature.read(), 'touches')
    others = [(item, touches) for item, touches in _in_progress() if item.id != feature.id]

    if not args.force and len(others) >= WIP_CAP:
        print(f'error: {len(others)} features are already In Progress; the cap is {WIP_CAP}.', file=sys.stderr)
        for item, _ in others:
            print(f'  {item.id}  {read_frontmatter(item.read()).get("title", "")}', file=sys.stderr)
        print('\nFinish or park one of those first, or pass --force and say why in a note.', file=sys.stderr)
        return 1

    if not mine:
        print(f'warning: {feature.id} declares no `touches:` — collisions cannot be checked.', file=sys.stderr)
        print(f'  python project/board.py touches {feature.id} <area> [<area> …]', file=sys.stderr)

    clashes = [(item.id, sorted(set(mine) & set(touches))) for item, touches in others if set(mine) & set(touches)]
    if clashes and not args.force:
        print(f'error: {feature.id} overlaps work already in flight:', file=sys.stderr)
        for other_id, shared in clashes:
            print(f'  {other_id} also touches {", ".join(shared)}', file=sys.stderr)
        print('\nTwo sessions must never own the same file. Wait, or narrow what', file=sys.stderr)
        print('this feature touches, or pass --force if you have read both diffs.', file=sys.stderr)
        return 1

    feature.write(set_frontmatter(feature.read(), 'status', 'In Progress'))
    print(f'{feature.id}: status = In Progress')
    if clashes:
        print(f'  forced past an overlap with {", ".join(other_id for other_id, _ in clashes)}')
    return 0


def cmd_add_subtask(args: argparse.Namespace) -> int:
    _append_to_section(find(args.id), 'Subtasks', f'- [ ] {args.text}')
    print(f'{args.id}: added subtask')
    return 0


def cmd_note(args: argparse.Namespace) -> int:
    item = find(args.id)
    stamp = dt.date.today().strftime('%Y-%m-%d')
    _append_to_section(item, 'Notes', f'- **{stamp}** — {args.text}')
    print(f'{item.id}: noted')
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    """Tick the nth unchecked box in a section (1-based, in document order)."""
    item = find(args.id)
    text = item.read()
    section = _section_bounds(text, args.section)
    if section is None:
        die(f'{item.id} has no "## {args.section}" section')
    start, end = section

    body = text[start:end]
    boxes = list(re.finditer(r'^(\s*)- \[( |x)\] ', body, re.MULTILINE))
    if not 1 <= args.n <= len(boxes):
        die(f'{item.id} "{args.section}" has {len(boxes)} item(s); asked for #{args.n}')

    box = boxes[args.n - 1]
    if box.group(2) == 'x':
        print(f'{item.id}: item {args.n} was already checked')
        return 0

    ticked = body[: box.start()] + box.group(0).replace('- [ ]', '- [x]') + body[box.end() :]
    item.write(text[:start] + ticked + text[end:])

    line_end = ticked.find('\n', box.start())
    print(f'{item.id}: ✓ {ticked[box.end() : line_end if line_end != -1 else None].strip()}')
    return 0


def cmd_set(args: argparse.Namespace) -> int:
    item = find(args.id)
    text = item.read()

    if item.kind == 'ADR':
        if args.value not in ADR_STATUSES:
            die(f'ADR status must be one of {", ".join(ADR_STATUSES)}')
        if args.value == 'Superseded' and not args.by:
            die('superseding an ADR requires --by ADR-…')
        text = set_frontmatter(text, 'status', args.value)
        if args.by:
            successor = find(args.by).id
            text = set_frontmatter(text, 'superseded_by', successor)
            text = re.sub(
                r'^## Status\n\n.*$', f'## Status\n\n{args.value} by [[{successor}]]', text, flags=re.MULTILINE
            )
        else:
            text = re.sub(r'^## Status\n\n\w+', f'## Status\n\n{args.value}', text, flags=re.MULTILINE)
        item.write(text)
        print(f'{item.id}: status = {args.value}')
        return 0

    if args.value == 'Done':
        die(
            'Done is not a status you type — it is the merge commit on '
            f'{main_branch()}. Merge the branch with `--no-ff` and the board reports it.'
        )
    if args.value == 'In Progress' and item.kind == 'FEAT':
        die(f'use `board.py start {item.id}` — it checks the clarify gate, the cap and the overlaps')
    if args.value not in WORK_STATUSES:
        die(f'status must be one of {", ".join(WORK_STATUSES)}')

    item.write(set_frontmatter(text, 'status', args.value))
    print(f'{item.id}: status = {args.value}')
    return 0


def cmd_clarifications(args: argparse.Namespace) -> int:
    """Exit non-zero while any marker is live. The gate `/new-feature` calls."""
    item = find(args.id)
    live = _live_clarifications(item)
    if not live:
        print(f'{item.id}: clear')
        return 0
    for location, marker in live:
        print(f'{location}: {marker}')
    return 1


def _derived_status(fm: dict[str, str], merged: set[str]) -> str:
    return 'Done' if fm.get('id', '') in merged else fm.get('status', '?')


def cmd_list(args: argparse.Namespace) -> int:
    directory, label = {
        'features': (FEATURES, 'FEAT'),
        'stories': (STORIES, 'STORY'),
        'decisions': (DECISIONS, 'ADR'),
    }[args.what]

    merged = _merged_ids() if label == 'FEAT' else set()
    rows: list[tuple[str, str, str]] = []
    for path in sorted(directory.glob(f'{label}-*.md')):
        fm = read_frontmatter(path.read_text(encoding='utf-8'))
        status = _derived_status(fm, merged) if label == 'FEAT' else fm.get('status', '?')
        if args.feature and fm.get('feature') != args.feature:
            continue
        if args.status and status != args.status:
            continue
        rows.append((fm.get('id', path.stem), status, fm.get('title', '')))

    if not rows:
        print('(nothing matches)')
        return 0

    for item_id, status, title in rows:
        print(f'{item_id}  {status:<12}  {title}')
    print(f'\n{len(rows)} {args.what}')
    return 0


def cmd_lanes(args: argparse.Namespace) -> int:
    """One view of everything in flight, read from the repo rather than stored.

    Board status, branch, worktree and declared areas in one table, with a warning
    wherever two live features name the same area. Nothing here is a second copy of
    something git already knows.
    """
    del args
    branches, worktrees = _branches(), _worktrees()
    live = _in_progress()

    if not live:
        print('Nothing In Progress. Free to start anything.')
        return 0

    print(f'{"FEATURE":<22} {"BRANCH":<8} {"TREE":<6} TOUCHES')
    print('─' * 78)
    for item, touches in live:
        fm = read_frontmatter(item.read())
        print(
            f'{item.id:<22} '
            f'{("yes" if item.id in branches else "—"):<8} '
            f'{("yes" if item.id in worktrees else "—"):<6} '
            f'{", ".join(touches) or "(undeclared)"}'
        )
        print(f'  {fm.get("title", "")}')

    warnings: list[str] = []
    for index, (item, touches) in enumerate(live):
        for other, other_touches in live[index + 1 :]:
            shared = sorted(set(touches) & set(other_touches))
            if shared:
                warnings.append(f'{item.id} and {other.id} both touch {", ".join(shared)}')
        if item.id not in branches:
            warnings.append(f'{item.id} is In Progress with no branch — is it actually started?')
        if not touches:
            warnings.append(f'{item.id} declares no `touches:`, so collisions cannot be checked')

    print()
    if warnings:
        for warning in warnings:
            print(f'⚠  {warning}')
    else:
        print('✓ No overlaps. Every live feature owns its own area.')

    if len(live) > WIP_CAP:
        print(f'⚠  {len(live)} features in flight; the cap is {WIP_CAP}.')

    stale = [p for p in (WORKTREES.iterdir() if WORKTREES.exists() else []) if p.is_dir()]
    orphans = [p.name for p in stale if not any(p.samefile(w) for w in worktrees.values() if Path(w).exists())]
    if orphans:
        print(f'⚠  Worktree directories git does not know about: {", ".join(orphans)}')
    return 0


# ---------------------------------------------------------------------------
# Section helpers
# ---------------------------------------------------------------------------


def _section_bounds(text: str, heading: str) -> tuple[int, int] | None:
    """Byte range of a `## heading` section's body, excluding the heading line."""
    match = re.search(rf'^## {re.escape(heading)}\s*$', text, re.MULTILINE)
    if not match:
        return None
    start = match.end()
    following = re.search(r'^## ', text[start:], re.MULTILINE)
    end = start + following.start() if following else len(text)
    return start, end


def _append_to_section(item: Item, heading: str, line: str) -> None:
    text = item.read()
    bounds = _section_bounds(text, heading)
    if bounds is None:
        die(f'{item.id} has no "## {heading}" section')
    start, end = bounds
    body = text[start:end].rstrip('\n')
    item.write(f'{text[:start]}{body}\n{line}\n\n{text[end:]}')


def mask_comments(text: str) -> str:
    """Blank out HTML comments while preserving line numbering.

    The templates explain the `[NEEDS CLARIFICATION: …]` syntax by showing it, inside a
    comment that spans several lines. Scanning for the marker without masking first
    would treat that comment as a live question and permanently block every new feature.
    """

    def blank(match: re.Match[str]) -> str:
        # Keep the newlines so every later line keeps its number.
        return ''.join(c if c == '\n' else ' ' for c in match.group(0))

    return re.sub(r'<!--.*?-->', blank, text, flags=re.DOTALL)


def _live_clarifications(feature: Item) -> list[tuple[str, str]]:
    """Every unresolved marker across the feature file and its requirements page.

    Scans the whole text rather than line by line, which is the difference between the
    gate working and not: a marker wrapped across two lines matches nothing under a
    per-line scan, and a feature carrying a genuinely unresolved question sails past.
    Markers are reported at the line they *start* on.
    """
    found: list[tuple[str, str]] = []
    for path in (feature.path, requirements_path(feature.id)):
        if not path.exists():
            continue
        masked = mask_comments(path.read_text(encoding='utf-8'))
        for match in CLARIFICATION_RE.finditer(masked):
            lineno = masked.count('\n', 0, match.start()) + 1
            found.append((f'{path.relative_to(ROOT)}:{lineno}', match.group()))
    return found


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='board.py', description=SUMMARY)
    sub = parser.add_subparsers(dest='command', required=True)

    p = sub.add_parser('new-feature', help='allocate a feature (and, on the full track, its requirements page)')
    p.add_argument('name')
    p.add_argument(
        '--track',
        choices=TRACKS,
        default='full',
        help='story: criteria on the feature, one story, no requirements page. See project/CLAUDE.md.',
    )
    p.add_argument('--touches', nargs='*', default=[], help='the areas this feature will edit')
    p.set_defaults(func=cmd_new_feature)

    p = sub.add_parser('new-story', help='allocate a story under a feature')
    p.add_argument('name')
    p.add_argument('--feature', required=True)
    p.set_defaults(func=cmd_new_story)

    p = sub.add_parser('new-adr', help='allocate a decision record')
    p.add_argument('title')
    p.add_argument('--feature')
    p.set_defaults(func=cmd_new_adr)

    p = sub.add_parser('touches', help='declare or show the areas a feature will edit')
    p.add_argument('id')
    p.add_argument('paths', nargs='*')
    p.set_defaults(func=cmd_touches)

    p = sub.add_parser('start', help='move a feature to In Progress, checking the cap and the overlaps')
    p.add_argument('id')
    p.add_argument('--force', action='store_true', help='past the cap or an overlap, deliberately')
    p.set_defaults(func=cmd_start)

    p = sub.add_parser('add-subtask', help='append a subtask to a story')
    p.add_argument('id')
    p.add_argument('text')
    p.set_defaults(func=cmd_add_subtask)

    p = sub.add_parser('note', help='append a dated note')
    p.add_argument('id')
    p.add_argument('text')
    p.set_defaults(func=cmd_note)

    p = sub.add_parser('check', help='tick the nth box in a section')
    p.add_argument('id')
    p.add_argument('n', type=int)
    p.add_argument('--section', default='Acceptance criteria')
    p.set_defaults(func=cmd_check)

    p = sub.add_parser('set', help='set a field')
    p.add_argument('id')
    p.add_argument('field', choices=['status'])
    p.add_argument('value')
    p.add_argument('--by', help='for ADR status Superseded: the successor id')
    p.set_defaults(func=cmd_set)

    p = sub.add_parser('clarifications', help='list live markers; exits 1 if any')
    p.add_argument('id')
    p.set_defaults(func=cmd_clarifications)

    p = sub.add_parser('list', help='list board items')
    p.add_argument('what', choices=['features', 'stories', 'decisions'], nargs='?', default='features')
    p.add_argument('--feature')
    p.add_argument('--status')
    p.set_defaults(func=cmd_list)

    p = sub.add_parser('lanes', help='what is in flight, and what collides')
    p.set_defaults(func=cmd_lanes)

    return parser


def main(argv: list[str] | None = None) -> int:
    for directory in (FEATURES, STORIES, REQUIREMENTS, DECISIONS):
        directory.mkdir(parents=True, exist_ok=True)
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == '__main__':
    raise SystemExit(main())
