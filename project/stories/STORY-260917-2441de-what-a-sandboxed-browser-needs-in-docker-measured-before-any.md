---
id: STORY-260917-2441de
title: What a sandboxed browser needs in Docker, measured before anything is built on it
feature: FEAT-260917-250f5a
status: Done
created: 2026-09-17
---

# STORY-260917-2441de — What a sandboxed browser needs in Docker, measured before anything is built on it

Part of [[FEAT-260917-250f5a]].

## Description

**Done on 2026-09-17, before the requirements were written.** Throwaway containers built from
`harry:6220e5c`, answering what a sandboxed browser actually needs here — and what it costs.
Every row of the table on the requirements page came from these runs.

The findings that decided the design: the sandbox will not start under Docker's default seccomp;
the profile everyone links to is too old for this runtime to start a container with at all; and
`playwright run-server` in a second container gives a headed, sandboxed browser that reads De Tijd
while holding nothing.

## Acceptance criteria

- [x] Whether a non-root user can drive the browser at all is measured, including where the browsers must be installed for it
- [x] Whether `chromium_sandbox=True` starts under Docker's default seccomp is measured, and what does let it start
- [x] Whether a maintained seccomp profile is available is settled — the well-known one is tried on this runtime
- [x] Whether a browser in a second container can be driven headed and sandboxed, read De Tijd at 200, and hand its cookies back is measured
- [x] Whether that second container can be kept free of credentials is checked from inside it
- [x] The findings are on the requirements page as a table, with the date and the image they came from
- [x] Nothing from the spike is committed, and its containers, network and image are deleted

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

