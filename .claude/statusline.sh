#!/usr/bin/env bash
# Status line: branch, the work id it encodes, uncommitted count, and the two flags
# worth interrupting for — the safety unlock, and a gate someone else is holding.
set -uo pipefail

# symbolic-ref, not rev-parse --abbrev-ref: on a repo with no commits yet the latter
# prints `HEAD` to stdout *and* fails, so the fallback appends to it rather than
# replacing it and the status line reads `HEAD\n-`.
branch=$(git symbolic-ref --quiet --short HEAD 2>/dev/null \
  || git rev-parse --short HEAD 2>/dev/null \
  || echo '-')

# feat/FEAT-260912-a1b2c3-slug -> FEAT-260912-a1b2c3
work_id=$(echo "$branch" | grep -oE '(FEAT|STORY)-[0-9]{6}-[0-9a-f]{6}' | head -1)

dirty=$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')

line="🐦 ${branch}"
[ -n "$work_id" ] && line="${line} • ${work_id}"
[ "${dirty:-0}" != "0" ] && line="${line} • ${dirty}✎"
[ -d .claude/.gate.lock ] && line="${line} • 🔒 gate running"
[ -f .claude/.unlock-safety ] && line="${line} • 🔓 unlocked"

echo -e "$line"
