---
id: FEAT-260915-2a6ce1
title: Harry runs on the NUC, with a dev stack beside the real one
track: full
created: 2026-09-15
touches: [Dockerfile, compose, core, docs, scripts]
stories: [STORY-260915-e0628f, STORY-260915-1b871c, STORY-260915-843c7d, STORY-260915-36ccd2]
decisions: [ADR-260915-8882ef]
---

# FEAT-260915-2a6ce1 — Harry runs on the NUC, with a dev stack beside the real one

## Summary

Harry works on a laptop and has never run in a container. This puts it on the NUC, on all the
time, restarting with the machine — and puts a **dev stack beside it** on the same box, with
its own port, data and credentials, so a change can be tried without touching the morning.

The plan is on the requirements page and is written to be picked up by a session with no
memory of the one that wrote it. Start by reading `docker-compose.yml` — it exists and `make
up` works today, so the job is to extend it, not to write one. Scenario 1 is the acceptance
test that needs no credentials, and it is not "everything is skipped": weather and news
declare no required setting and load on a bare machine.

## Acceptance criteria

- [x] `make up` starts Harry on a machine with no `.env.local` anywhere; weather and news load, and icloud, remarkable and slack are skipped, each naming the setting it is missing
- [x] Nothing crashes on that first boot — a capability whose configuration is absent disables itself
- [x] Each credential put on the NUC turns its capability from skipped to loaded without a rebuild
- [x] No credential is in the repository, in the image, or in a committed compose file
- [x] A dev stack runs beside the real one with its own port, data directory and credentials
- [x] The dev stack's scheduler is off, so it can never report a deadline the real one met
- [x] Stopping or rebuilding either stack leaves the other running
- [x] A page is built inside the container through `scripts/call_tool.py`, written under the data volume, with nothing pushed
- [ ] Harry restarts with the machine and keeps its data across a reboot
- [x] Every build is tagged with something that cannot be reused, the real service names a tag, and going back to the previous one is one command
- [x] `xvfb` is in the image and nothing uses it yet, so the De Tijd feature does not have to rebuild it
- [x] `docs/operating.md` describes what is actually on the NUC, in the present tense

## Stories

<!-- Maintained by `board.py new-story`. -->
- [ ] [[STORY-260915-e0628f]] — A compose file, and Harry starts with nothing configured
- [ ] [[STORY-260915-1b871c]] — A dev stack beside the real one, with its scheduler off
- [ ] [[STORY-260915-843c7d]] — The credentials reach the NUC, one capability at a time
- [ ] [[STORY-260915-36ccd2]] — Deploying a version, and going back to the last one

## Notes

<!-- Appended by `board.py note`. -->
- **2026-09-15** — Criterion 9 ('restarts with the machine and keeps its data across a reboot') is half proven and deliberately not ticked. Proven: restart: unless-stopped is live — killing the python process inside the container brought it back healthy on its own with RestartCount=1 — and the named volume survives make down followed by make up, and survives a deploy and a rollback. Not proven: an actual reboot of the NUC, which nobody has done since Harry was containerised. Tick it after the next reboot, or reboot deliberately and tick it then. Note that docker kill and docker stop count as manual intervention, so unless-stopped correctly does not restart after those — crash the process inside the container instead, or you will conclude the policy is dead when it is not.

## Links

- Requirements: [[FEAT-260915-2a6ce1]]
- Decision: [[ADR-260915-8882ef]] — One image, two compose profiles

