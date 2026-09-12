---
paths:
  - ".harry/**"
  - "tests/**"
---

# Everything outside Harry will break, and the page still renders

Harry's dependencies are a set of RSS feeds, a newspaper that blocks scripted clients, a
reverse-engineered tablet protocol, and Apple's least reliable CalDAV surface. Every one of
them has already failed or is documented as failing.

## Never

- Reach a live URL from a test. Not in the gate, not "just this one", not in a fixture
  builder
- Let one source's failure reach another section. A dead feed is a line of text on the page
- Retry a failing external call forever, or without a ceiling
- Fall back silently. A fallback that nobody is told about is a page that quietly got worse
- Pin an external client loosely when its protocol is reverse-engineered

## Always

- **Record the failure as a fixture.** A 403 from De Tijd, a malformed Atom entry, a
  reMarkable write rejection — save the real response in `tests/fixtures/` and assert
  against it. That is how the degraded path gets a test at all
- Give every section an independent failure boundary. It prints "<source> unavailable" and
  the page renders
- Say what happened, to a person. A source that fell back, a credential that lapsed, a push
  that failed twice — all three reach Slack. See **Alerting** in `CLAUDE.md`
- Mark a test that genuinely needs a real service `live`. It runs from `make test-live`,
  never from the gate
- Pin `rmapi` and `remarkapy` to exact versions. reMarkable broke every write in August 2026
  and needed a patched client; expect that a few times a year

## Why

A morning page that lost its best source three weeks ago looks exactly like a morning page
that had nothing from that source today. There is no way to notice the difference from the
page, which is why the alert is part of the feature rather than a nicety.

Fixtures rather than live URLs is the difference between a suite you can run on a train and
a suite that fails for a reason that has nothing to do with your change. It also makes the
degraded path testable, which is the only way `inert-controls.md` can be satisfied at all.

## Common rationalizations

| Excuse | Reality |
|---|---|
| "The feed is always up" | VRT NWS is. `tijd.be/rss/top_stories.xml` is a 404 that used to work. |
| "A live test catches real breakage" | It catches it on a random Tuesday, in the gate, during unrelated work. Mark it `live`. |
| "The fallback is obviously fine" | Then say so out loud, in Slack, when it happens. |
| "Version ranges get us fixes faster" | They also get you the release that broke every write. |

## Enforcement

`.claude/agents/pre-close-verifier.md` greps the diff for `http://` and `https://` in
`tests/**` and for a new external call with no degraded path or alert. Severity:
**Critical** for a missing alert, **Important** for a live URL in the gate — cite
**Degrading** or **Alerting**.
