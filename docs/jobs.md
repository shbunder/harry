# Jobs: Harry's clock, and the clock Harry only watches

Two halves, and the second is the one that matters.

**Harry owns the clock for its own heuristic work.** Refresh a cache at 05:00, retry a
failed push, check a credential. Each is a rule that can be written down in advance, so
Harry runs it.

**Harry does not own the clock for anything that needs judgement.** A Claude scheduled task
fires the morning page, because choosing what goes on it is the whole reason Harry never
calls a model.

That split costs one thing: **an external trigger cannot report its own absence.** A
scheduled task that never fires produces silence, and silence looks exactly like a morning
you did not check. The watchdog is the only thing that tells those two apart.

## A job Harry runs

```yaml
---
name: refresh-feeds
description: Re-fetch every configured feed, so the morning ask is instant
trigger: schedule
schedule: "0 5 * * *"          # five cron fields
timezone: Europe/Brussels      # required — 05:00 is a local time
enabled: true
---
```

With a `job.py` beside it registering what to run. Harry schedules it and:

- **One at a time.** If a run is still going when the next fire time arrives, the second
  does not start and Harry logs `skipped <job>: the previous run has not finished`. A cache
  refresh that has stopped answering wants one copy of itself, not a hundred.
- **A failure costs only that job.** The exception is logged, one Slack message names the
  job and what it raised, and everything else keeps its schedule. Keyed on the job, so one
  failing every five minutes reports once a day.
- **A missed window is not made up.** A machine asleep through three fire times runs the job
  once on waking. If Harry was off, the job did not run — and if that mattered, it had a
  deadline.
- **A `trigger: schedule` job with no `job.py`** would sit in `/health` looking installed and
  never do anything. Harry says so in Slack instead.

## A job Claude runs

```yaml
---
name: morning-page
description: The day's weather, agenda and a few full articles, on the tablet by 07:00
trigger: claude
deadline: "07:00"              # what the watchdog checks
timezone: Europe/Brussels
enabled: true
---
```

Harry never fires this. A Claude scheduled task does, at a time it owns, and asks Harry for
the brief — which is this file's body, served as an MCP prompt named for the job.

**The brief must end by telling Claude to call `harry_mark_done`:**

> When the page is on the tablet, call `harry_mark_done("morning-page")`. Harry has no other
> way of knowing you were here, and without it you will get a "has not run today" message
> about a page you are holding.

That sentence is the whole mechanism. Harry cannot infer that the work happened — inferring
is judgement, and judgement is Claude's half.

## What the watchdog checks

**Every five minutes, and once when Harry starts.** For each `trigger: claude` job with a
deadline:

> Has the deadline passed today, in that job's own timezone, and has nothing finished it
> since midnight there?

If so, one message:

```
morning-page has not run today. It was due by 07:00.
```

**Once a day, even across a restart.** The date already reported is written down next to the
completion, under the data volume. The alert layer's own 24-hour suppression is in memory,
which is right for a fault repeating every five minutes and wrong for one reported once a
day — the second message would arrive on every deploy.

**Polling, not a check scheduled at the deadline.** A check set for exactly 07:00 does not
run if Harry was switched off at 07:00, which is precisely the morning worth hearing about.
Polling gets you the answer at most five minutes late instead of never, and a machine that
comes back at 07:20 reports the 07:00 miss when it starts.

**A failed alert does not count as reported.** If Slack was down, the date is not written
and the next check tries again. Marking it would mean the one morning it mattered went
unheard.

## What it cannot notice

- **Harry switched off all day.** Nothing reports it, and nothing inside Harry can. Same
  shape as the hole in [alerting.md](alerting.md): the thing that reports failures cannot
  report its own absence.
- **Work done without the call.** If Claude builds the page and never calls
  `harry_mark_done`, you get a "has not run today" message about a page you are holding.
  That is the deliberate direction to be wrong in — a false alarm gets noticed and fixed, a
  silent miss does not.
- **A job with no `deadline:`.** There is nothing to notice. `.claude/rules/capability-shape.md`
  requires one on every `trigger: claude` job for exactly this reason, and `make lint`
  enforces it.

## What Harry remembers

One file, under the data volume:

```bash
cat /data/jobs.json
```

```json
{
  "jobs": {
    "morning-page": {
      "finished": "2026-09-13T06:45:12.481+02:00",
      "reported": "2026-09-12"
    }
  }
}
```

Two facts per job: when it last finished, and which deadline has already been reported. Not
SQLite — this is a handful of keys read once at start-up and written a few times a day, and
a file you can read while wondering why the watchdog is quiet is worth more than an index.

If the file cannot be read, Harry starts with an empty record and says so, and the next
check alerts for everything. A false alarm is the safe direction; refusing to start because
a cache file is unreadable is not. If it cannot be written, that is logged every time — a
read-only data volume is a real problem.
