# Debug in five steps

Reproduce → Localize → Reduce → Fix → Guard.

## Never

- Delete, skip, or `xfail` a failing test to make the suite green
- Lower `fail_under` in `pyproject.toml`, or raise `max-complexity`, to make the gate pass
- Change a test's assertion to match what you observed, unless you can say in one sentence
  why the old assertion was wrong
- Mark a test `live` to get it out of the gate when what it actually needs is a fixture
- "Fix" something you could not first reproduce

## Always

1. **Reproduce** — a deterministic failure, ideally as a test
2. **Localize** — bisect until you know which layer is lying
3. **Reduce** — strip the reproduction to its smallest form
4. **Fix** — change the cause, not the symptom
5. **Guard** — leave the reproduction behind as a test that fails without the fix

## Why

Both numbers in `pyproject.toml` are ratchets: coverage only rises, complexity only falls.
A build made green by moving one has not been fixed, it has been hidden, and the next
person inherits both the bug and a weaker gate.

Step 5 is the one that gets skipped and the one that matters. A bug without a guard is a
bug you will fix twice. What that guard must look like is
[`inert-controls.md`](inert-controls.md).

The `live` marker deserves its own line because it is the easy exit here. It exists for
tests that genuinely need a paired tablet or a real iCloud account. Moving a feed-parsing
test behind it because the fixture is awkward takes that test out of the gate permanently,
and nobody runs `make test-live` on a Tuesday.

## Common rationalizations

| Excuse | Reality |
|---|---|
| "The test was flaky anyway" | Flaky means it is telling you about a race. That is a finding. |
| "Coverage dropped because I added error handling" | Then test it. That branch is the one most likely to be wrong. |
| "I don't need to reproduce it, I know what it is" | You know what *a* bug is. Find out if it is the one you're seeing. |
| "It's a one-line fix" | One-line fixes have the worst regression rate, because nobody guards them. |
| "The feed changed, so the test is wrong" | Then record the new feed as a fixture and assert the new shape. |

## Enforcement

`.claude/agents/pre-close-verifier.md` diffs test files for deletions, `pyproject.toml` for
threshold changes, and the diff for newly added `live` markers. Severity: **Critical**.
