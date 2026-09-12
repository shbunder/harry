# Docs ship with the change

A feature that is not documented is not finished.

## Never

- Merge a change a person operates — a new credential, a new job, a new tool — with a
  "docs to follow"
- Describe behaviour you intend to build in the present tense
- Document a setting only in `config.py`. The person setting it up is reading `docs/`

## Always

- Update the affected page in the same commit as the code
- A new module gets a page saying: what it does, what it needs in `.env`, how to get those
  values, what it does when its source is unavailable, and what it puts in Slack when that
  happens
- Keep examples runnable, with realistic values
- Write what Harry does **today**. What an earlier version got wrong belongs in git history
  and on the board, not on the page

## Why

Documentation written later is written from memory, by someone who has stopped being
confused by the thing they are describing. The moment you understand a subsystem well enough
to change it is the only moment you can explain it well.

Harry's operational documentation is load-bearing in a way most is not. Two of its
credentials expire on their own schedule and have to be renewed by hand. The page that says
*how* is the difference between a ten-minute job and an afternoon of rediscovery.

## Common rationalizations

| Excuse | Reality |
|---|---|
| "It's for me, nobody reads it" | You in three weeks. The next agent, with no memory. |
| "The code is self-documenting" | The code documents *what*. Docs document *why* and *when not to*. |
| "I'll do a docs pass at the end" | The end is where scope gets cut. Docs get cut first. |
| "The re-login steps are obvious" | They were, on the day you worked them out. |

## Enforcement

`.claude/agents/pre-close-verifier.md` checks that a diff adding a module, a credential or a
scheduled job also touches `docs/`. Severity: **Important**.
