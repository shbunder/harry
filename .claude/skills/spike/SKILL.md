---
name: spike
description: Answer one risky unknown with a throwaway script before building on it. Use for a Phase 0 question, or any time a plan depends on something nobody has run yet — an API that might not work, a limit nobody has measured, a client that might be dead.
---

Spike: $ARGUMENTS

A spike answers **one** question, prints `PASS` or `FAIL`, and is never imported by
anything. It costs half an hour and it is the cheapest thing in this repo.

### 1. Say the question, and what each answer changes

Write it down before writing code, in one line each:

- **The question** — *"Does an MCP tool call that blocks for five minutes still return?"*
- **If it passes** — *"`ask_human` holds the call open, and the Slack loop is what the plan
  describes."*
- **If it fails** — *"`ask_human` returns a request id and the session polls `check_answer`.
  More turns, same outcome, different module."*

A spike whose failure changes nothing is not worth running. Say so and skip it.

### 2. Write it in `scratch/`

```
scratch/<short-name>.py
```

Everything in `scratch/` except its README is gitignored, so this never reaches the repo and
never gets imported. It may be ugly. It may hardcode a value. It must print its result:

```python
print('PASS — De Tijd article body, 4,211 chars, extracted with trafilatura')
print('FAIL — 403 with the saved session; the cookie is 31 days old')
```

Run it:

```bash
make spike S=<short-name>
```

### 3. Use real credentials, and keep them where they live

A spike that mocks the thing it is testing has tested nothing. Read the real values
through `harry.config` — they come from `.env.local`, which is gitignored. Never paste a
token into the script, and never put one in `.env`, which is committed. The reMarkable device
token grants complete read and write access to the tablet; the De Tijd storage state is a
live login. See `.claude/rules/secrets-and-config.md`.

### 4. Record the finding where the decision lives

This is the step that makes a spike worth more than a terminal scroll.

- **It settled a design choice** → the finding goes into the ADR, in *Decision drivers* or
  *Considered options*, with the number you measured.
- **It settled a requirement** → it goes into the scenario, as the number on the line.
- **It failed** → say what the plan now does instead, and where that is written down.

Quote the actual output. "It worked" is not a finding; "a 5-minute blocking call returned,
`MCP_TOOL_TIMEOUT` defaulted to 600s, and 11 minutes was refused" is.

### 5. Report

The question, the answer in one line, the evidence, and what changes in the plan. Then say
which spike is worth running next, or that the phase is clear.

### The six Phase 0 spikes

`scratch/README.md` lists them with what each one proves. Three matter most: a De Tijd
article body on stdout, an MCP tool call that survived five minutes, and a Claude scheduled
task reaching Harry over the tunnel — that last one is the morning page's trigger, so
nothing in Phase 1 is safe to build until it passes.
