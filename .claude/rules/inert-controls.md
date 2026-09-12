# A control that cannot fail is not a control

Every gate, limit, retry, alert and fallback in Harry exists because something real broke.
A test that goes green whether or not the control is there has recorded a belief, not a
behaviour.

This rule also covers the sibling defect: **a list, roster, glob or registry that nothing
executes.** Completeness is proved by something that runs.

## Never

- Assert a setting instead of the behaviour it is supposed to produce.
  `assert settings.retry_count == 2` is not a claim that anything retried
- Call the function beneath the path production takes. If production reaches it through
  the MCP tool, the route, or the scheduler, the test goes in the same way
- Add a module, a feed, a section or a tool to a list and consider it wired. Ask what
  *executes* the list
- Write a negative assertion against a string literal that appears nowhere else
- Leave a fallback path with no test that takes it

## Always

- For every control, ask the deciding question: **delete the gate, and which test goes
  red?** If the answer is "none", you have found one
- Test the degraded path as deliberately as the happy one. A feed that 404s, a browser
  session that expired, a push that failed twice — each gets a test that makes it happen
- Name who populates a field in production. If the answer is "nothing yet", the control is
  inert and the feature is not done, whatever the suite says
- When a test's truth depends on something untracked — an installed browser, a reachable
  host, a built image — say so at the assertion, and mark it `live`

## Why

Harry's whole design is degradation and alerting. Both are invisible when they work, which
means both are invisible when they do not. The morning page that silently drops De Tijd for
three weeks looks exactly like the morning page that never had a De Tijd article that day.

The alerting path is the worst case: an alert that does not fire is discovered by the
absence of something you were not expecting. **Test that the alert fires, not that the code
that would send it exists.**

## Common rationalizations

| Excuse | Reality |
|---|---|
| "The flag is obviously read" | On which branch? Take it and see. |
| "It's just config" | Config is how a gate gets turned off in production. |
| "The list is checked by the type checker" | The type checker proves it parses, never that anything reads it. |
| "I'll add the failure test later" | The failure path is the one you will never exercise by hand. |
| "Mocking the failure is unrealistic" | Recording the real failure once, as a fixture, is neither. |

## Enforcement

`.claude/agents/pre-close-verifier.md` builds a table of every control in the diff and asks
the three questions. Severity: **Critical** where the control cannot fail, **Important**
where it arrives by a path production never takes.
