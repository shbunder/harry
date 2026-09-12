---
name: new-adr
description: Record an architecture decision on Harry's board using the MADR template. Use when a choice would make a future reader ask "why did they do it that way?" — a transport, a storage layout, a dependency pin, a credential model, a change to the module contract.
---

Record a decision about: $ARGUMENTS

### 1. Check it is not already decided

```bash
ls project/decisions/
grep -rln "<topic keywords>" project/decisions/
```

If an ADR already covers this, you are either amending it or superseding it. Amend when the
decision stands and the context grew; supersede when the decision changed.

### 2. Check it deserves one

`project/CLAUDE.md`: reserve an ADR for a real boundary. A transport, a storage layout, a
credential model, a pin on something reverse-engineered, a change to `registry.py` or
`sdk.py`. A decision nobody would contest does not need a record — say so and put the reason
in a code comment instead.

### 3. Allocate

```bash
uv run python project/board.py new-adr "<title>" --feature FEAT-…
```

`--feature` links it both ways: the ADR names the feature it drives, and the feature's
`## Links` and `decisions:` both gain the id.

### 4. Write it

MADR, and the parts that carry weight:

- **Context & problem** — what forces the decision, written so someone who was not here can
  feel it.
- **Decision drivers** — what you are optimising for, in priority order.
- **Considered options** — **at least two, genuinely.** The rejected option gets a fair
  statement of its case. An ADR whose alternatives are strawmen is a rationalisation with a
  template around it.
- **Decision outcome** — active voice. *"Claude has the LLM; Harry performs heuristic work only."* Name the core principle that drove
  it, if one did.
- **Consequences** — the good and the bad. **Name what this makes harder.** That paragraph
  is the one people come back for.

### 5. Accept it

```bash
uv run python project/board.py set ADR-… status Accepted
```

`plan-verifier` blocks a feature that links a `Proposed` ADR. A decision left proposed is a
decision not made.

### 6. Commit

```bash
git add project/decisions/ADR-…-{slug}.md project/features/FEAT-…-{slug}.md
git commit -m "ADR-…: <title> (for FEAT-…)"
```

### 7. Report

The id, the outcome in one sentence, and what it makes harder.
