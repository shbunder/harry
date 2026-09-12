---
name: new-job
description: Add a job to Harry — something that happens on a trigger, declared as a markdown file under .harry/jobs/. Use for the morning page, a weekly summary, a cache refresh, a watchdog. No Python needed unless the job runs its own script.
---

Add a job for: $ARGUMENTS

A job is **something Harry does on its own** — on its own clock, or when a Claude scheduled
task asks. It is one folder under `.harry/jobs/` and, at minimum, one markdown file.
`.harry/README.md` has worked examples of both kinds.

### 1. Decide who owns the clock

This is the only question that matters, and it follows from whether the work needs
judgement.

| | `trigger: schedule` | `trigger: claude` |
|---|---|---|
| Fires | Harry's own scheduler | A Claude scheduled task |
| For | Pure heuristic work — refresh a cache, retry a push, check a credential | Anything that needs a decision: what to include, how to phrase it, what matters today |
| Needs | `schedule:` and `timezone:` | `deadline:`, so the watchdog can notice it never ran |

If you find yourself wanting Harry to choose, rank, summarise or phrase something, it is
`trigger: claude`. Harry does not reason — `.claude/rules/no-model-calls.md`.

### 2. Open the feature

```bash
/new-feature <what this makes possible, in your terms>
```

A heuristic job is usually the **story track**. A `trigger: claude` job is usually **full**:
it brings a brief, a deadline, and an alert path.

Declare `--touches .harry/jobs/<name>`.

### 3. Write the declaration

`.harry/jobs/<name>/JOB.md`. The `name` must match the folder.

```yaml
---
name: <name>
description: <what it does for you, not what it is>
trigger: claude                 # or: schedule
deadline: "07:00"               # trigger: claude — the watchdog alerts past this
schedule: "0 5 * * *"           # trigger: schedule — five cron fields
timezone: Europe/Brussels
requires: [<connector>, …]      # must already exist under .harry/connectors/
enabled: true
---
```

Never both `schedule:` and `trigger: claude`. Two clocks that can disagree is exactly what
ADR-260912-bd36c2 removed.

### 4. Write the body — or don't

**`trigger: claude`: the body is the brief.** Write it addressed to Claude, in your own
words, saying what to pick and what to skip. Harry serves it verbatim and never reads it.
This is the whole job definition in one file, even though Claude runs half of it.

It is published as an **MCP prompt** named for the job, so the scheduled task invokes the
prompt rather than calling a tool to fetch text — and the job appears in any MCP client's
prompt picker. Name the tools the brief expects Claude to call, so the sequencing lives
here rather than in a tool schema.

**`trigger: schedule`: the body is documentation.** Nothing serves it. Say what the job is
for and what happens when it fails, for whoever reads this in three weeks.

### 5. Compose tools; do not reimplement them

A job calls tools. The morning page calls `build_digest`; it does not know how to render a
PDF. If you are writing logic in a job that a tool already has, stop — two code paths for
the same work get fixed twice and drift in between.

If the tool you need does not exist yet, it belongs to a connector. Add it there.

### 6. Answer the failure questions before writing any code

1. **What happens when a `requires:` connector is down?** The job should degrade, not
   vanish. Say what still gets produced.
2. **What reaches Slack, and how often?** Once per failure or once per day — never once per
   retry.
3. **How would you know it never ran at all?** For `trigger: claude` the answer is the
   deadline. For `trigger: schedule` say so explicitly, even if the answer is "a stale cache
   shows up on the page, which is already reported".

### 6b. Settings, if it has any

A job's own settings go in its `config:` block and nowhere else — `article_limit` is read
by one job and has no business being global. `make env-template` writes the `.env` beside
the declaration; your values go in `.env.local` next to it.

### 7. Validate and test

```bash
uv run python scripts/check_capabilities.py
```

Catches a missing deadline, a schedule with no timezone, a name that disagrees with its
folder, and a `requires:` naming a connector that does not exist.

Then a test that makes the job's failure path happen — a required connector down, a tool
raising — and asserts what still gets produced and what gets sent.
`.claude/rules/inert-controls.md`.

### 8. Docs

A `trigger: claude` job also needs the Claude side written down: which scheduled task fires
it, and that the task's own prompt should be thin — "run the `<name>` job" — with the real
brief living in `JOB.md`.

### 9. Report

The job name, who owns its clock, what it needs, what it does when that is unavailable, and
how you would find out it never ran.
