---
id: FEAT-260912-74f222
title: Anything Claude makes can land on the tablet
track: full
created: 2026-09-12
touches: [connectors/remarkable]
stories: [STORY-260914-461f63, STORY-260914-6db95b]
decisions: [ADR-260914-6b0608]
---

# FEAT-260912-74f222 — Anything Claude makes can land on the tablet

## Summary

The output surface, and the one holding the most dangerous credential in the repo — the device token grants complete read and write access to every document on the tablet, with no scopes. The protocol is reverse-engineered and it does break: all writes failed in August 2026 and needed a patched client.

## Acceptance criteria

<!-- One box per scenario. These are what the pre-close-verifier builds its
     traceability matrix from. -->

- [x] A PDF is uploaded under the name given, inside the configured folder, and the answer says the folder and the id
- [x] A folder that does not exist is created once; the next push finds it rather than making a second
- [x] A push that fails once is retried exactly once, and a successful retry puts nothing in Slack
- [x] Two failed attempts raise, and put one line in Slack naming the tablet and why, once per 24 hours
- [x] A revoked token says so and says to re-pair, rather than reporting a network problem
- [x] The device token reaches no log line, no exception message and no Slack message
- [x] With no DEVICE_TOKEN the connector and both tools are skipped, saying what is missing, and the rest of Harry loads
- [x] `make remarkable-pair CODE=…` exchanges the code once and writes the token to the gitignored .env.local without printing it
- [x] `remarkable_push_document` takes either a PDF path or markdown text, and neither-or-both is an error naming which
- [x] Markdown is rendered at 509.34 by 679.13 points before it is pushed
- [x] `remarkable_list_documents` says what is in the folder, newest first, and an absent folder is an empty list
- [x] The push tool is readOnlyHint false and destructiveHint false; the list tool is readOnlyHint true; both defer
- [x] remarkapy is pinned to exactly 0.3.1 with the reason on the same line, and nothing needs a Go rmapi binary
- [x] A live test pushes a real page to a real tablet, marked live and never in the gate
- [x] docs/sources.md and the runbook say how to pair, what a failed push does, and what lands in Slack

## Stories

<!-- Maintained by `board.py new-story`. -->
- [x] [[STORY-260914-461f63]] — Harry can put a page on the tablet, and says so when it cannot
- [x] [[STORY-260914-6db95b]] — Claude can push a document to the tablet and see what is there

## Notes

<!-- Appended by `board.py note`. -->
- **2026-09-12** — PASS on the rendering half, ahead of the push. WeasyPrint 70.0 imports and renders on this Mac with no brew install pango needed, producing a 9,778-byte PDF at exactly 509.34 x 679.13 pt. The Paper Pro geometry is expressible in plain CSS @page, and the renderer is not a risk.
- **2026-09-12** — Finding against the plan: remarkapy 0.3.1 exposes register_device(code) and register_device_wizard(), so pairing needs no Go rmapi binary. The plan assumed rmapi for the one-time pairing. rmapi may still be worth having as a fallback pusher, but it is not on the critical path and the Dockerfile may not need it.
- **2026-09-13** — reMarkable spike PASS. Paired and pushed: a 9,778-byte PDF rendered at 509.34 x 679.13 pt reached the cloud as 77abc664-09ad-454f-993d-54b91a9a9683. No Connect subscription was needed for the upload to be accepted - pending confirmation it actually appears on the device. Pairing used remarkapy's own register_device(code); the Go rmapi binary was never installed, so the Dockerfile does not need it. Pin remarkapy 0.3.1 exactly: the protocol is reverse-engineered and a release broke every write in August 2026. Token is in ~/.rmapi, outside the repo.
- **2026-09-13** — CONFIRMED ON THE DEVICE. The pushed PDF appeared on the tablet, so the free tier carries cloud sync for a daily push and no Connect subscription is needed. That settles the question two implementers disagreed about. Caveat to carry forward rather than forget: the 50-day rule still applies to a document nobody touches, which is irrelevant for a page replaced every morning and relevant the moment the tablet becomes an archive.
- **2026-09-14** — Reflection: pre-close-verifier ran twice. First pass REQUEST CHANGES with three Critical — one alert key for every operation, so a failed listing silenced the 06:30 push; an unguarded persist_config that would have written the device token to ~/.rmapi; and the Go rmapi binary still in the image against its own accepted ADR. Second pass REQUEST CHANGES with four controls that could not fail, all test-only. Traceability 15/15 criteria to named tests, one marked by inspection. Degraded paths tested: cloud unreachable, slow, socket death, protocol rejection, revoked token, absent folder, no credential, refused pairing code. Scope drift: a listing cap that no criterion asked for, kept because tool-design.md requires one. Found outside the verifier: a bare pytest run was executing the live test and pushed eight copies of a test page to a real tablet.

## Links

- Requirements: [[FEAT-260912-74f222]]
- Decision: [[ADR-260914-6b0608]] — remarkapy is pinned to an exact version, and there is no Go rmapi binary


## Lessons Learned

### What worked

**A deliberately incomplete stand-in, plus a signature check against the real client.**
`StandIn` in `tests/test_remarkable_connector.py` implements exactly the four calls this
connector makes and nothing else, so a fifth call fails the suite rather than quietly
working. `test_the_stand_in_has_the_same_shape_as_the_real_client` compares each method's
parameters against `remarkapy.Client`, which is what stops the stand-in drifting into
fiction. **A hand-written double is safe when something independent checks its shape.**

**Recording what the service really returns, after guessing wrong.** The stand-in used ISO
timestamps because that is what a sensible API would send. reMarkable sends epoch
milliseconds in a string. Sorting still worked — 13-digit strings compare in the right
order — so nothing failed; the time shown to Claude was simply wrong. One real listing in
`tests/fixtures/remarkable/folder-listing.json` settled it. **Where a fixture was invented
rather than recorded, assume it is wrong in a way that still passes.**

**Making the write surface a property instead of a promise.**
`test_the_connector_only_ever_asks_for_four_things` greps the connector for `client.delete`,
`client.rename` and the rest. The token permits all of them; the connector offers none, and
a future edit that adds one fails a test rather than a review.

### What to do differently

**Make the test environment safe *before* probing a security control, not after.** Checking
a guard means deleting it and watching a test go red. The guard here stops a device token
being written to `~/.rmapi` — so deleting it wrote a real token into a real home directory,
twice. The fixture now redirects `DEFAULT_CONFIG_PATH` *and* `candidate_config_paths`;
moving only the first changed nothing, because the real file existed and was the first
candidate. **Before you delete a control to test it, ask what it was protecting and put that
out of reach.**

**A `live` marker is not a guard unless something enforces it.** `make check` and `make test`
passed `-m "not live"`; a bare `pytest tests/test_remarkable_connector.py` did not, and ran
the live test. Seven copies of a test page reached a real tablet before anybody noticed, and
the eighth arrived from a reviewer's sandbox that had copied `.env.local`. The flag now
lives in `addopts`, and `test_a_plain_pytest_run_cannot_reach_the_tablet` collects this file
in a subprocess to prove it. **A live test with a side effect on real hardware needs the
marker enforced at the lowest level anything runs at.**

**Four controls passed review and could not fail.** The page-size test built its own HTML
from the stylesheet constant rather than rendering what `render_markdown` produced — delete
the `<style>` and the page silently became A4. The escaping test asserted the output starts
with `%PDF`. The `-m "not live"` line had nothing watching it. **Ask the deciding question
per control, and when the answer is "the test builds the input itself", capture the real
input instead.**

**A dependency's module-level constant cannot be redirected by configuration.** remarkapy
computes its config path from `pathlib.Path.home()` at *import* time, so no environment
variable moves it; only an explicit `configfile` does. One missing keyword would have put a
tablet-wide credential in a plaintext file. **When a library writes credentials, find out
where it decides that, not where it documents it.**

### Patterns to reuse

- **`.harry/connectors/remarkable/connector.py`** — a lazily built client, because
  `remarkapy.Client.__init__` makes two network calls and start-up must not wait on
  somebody else's cloud; and `_trying(what, call, key)`, where the alert key is the
  *operation*, so a failed read cannot spend the day's alert budget before the 06:30 write.
- **`tests/test_remarkable_connector.py::no_network`** — replaces `httpx.Client` rather than
  injecting one, because injecting flips remarkapy's own `injected_runtime` flag, which is
  the thing under test. The docstring says so, which is the part worth copying.
- **`rendered_document()`** in the same file — captures the string a renderer hands
  WeasyPrint, so assertions are made against the real document rather than a rebuilt one.
- **`scripts/remarkable_pair.py`** — a one-shot credential exchange that writes the value and
  never prints it, into a temporary directory thrown away afterwards. Two independent locks,
  each with its own test.
- **`tests/fixtures/remarkable/README.md`** — a fixture directory that says which of its
  files are recordings, which are handmade, and which bug each one exists to catch.
