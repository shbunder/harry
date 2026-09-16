---
id: STORY-260916-c04a3c
title: Harry logs in to De Tijd by itself, once, and says when it cannot
feature: FEAT-260912-9c933f
status: Backlog
created: 2026-09-16
---

# STORY-260916-c04a3c — Harry logs in to De Tijd by itself, once, and says when it cannot

Part of [[FEAT-260912-9c933f]].

## Description

The half that makes the connector need nobody. When a page shows the paywall and the "Log in"
button, Harry logs in with the email and password, saves the session, and reads the page
again — once. When it cannot, it says so once and waits 6 hours before trying again, because
De Tijd's login service blocks an account after repeated failures.

## Acceptance criteria

- [ ] A logged-out page leads to exactly one login and one more read of the same article, in the same call
- [ ] A successful login saves the session and logs how many days the previous one lasted, when there was one
- [ ] A refused email or password answers `available: false` with a why that names the refusal and where the credentials live — and never contains the password
- [ ] A captcha, a code request, or a missing field stops the login within 60 seconds, with a why saying which
- [ ] After any failed login, no further attempt is made for 6 hours: five articles in an hour cause one login attempt, and each gets the same why
- [ ] A page that still shows the paywall after a successful login answers a why pointing at the subscription, and does not log in again
- [ ] A 403 never leads to a login attempt
- [ ] Through `news_article` over MCP, five De Tijd stories failing for one reason put exactly one line in Slack, naming De Tijd
- [ ] Each outcome of the login is decided by a function tested against recorded login pages, not only by the live test

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

