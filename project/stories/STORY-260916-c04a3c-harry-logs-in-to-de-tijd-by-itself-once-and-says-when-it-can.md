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

- [ ] A page with `paywall-active` leads to exactly one login and one more read of the same article, in the same call, within 2 minutes in all
- [ ] A successful login saves the session, writes the time to `logged-in-at`, and logs how many days the previous session lasted when a `logged-in-at` was there
- [ ] The login follows the table in the requirements' Scenario 8: consent, the login button on the homepage, email, password — each step waiting for its one expected ending
- [ ] `#error-element-password` answers the `refused` why, naming where the credentials live
- [ ] A captcha marker answers the `challenge` why; any other unexpected ending answers the `login-page` why, naming the step
- [ ] The whole login gives up within 60 seconds
- [ ] After `refused`, `challenge` or `login-page`, no further attempt is made for 6 hours: five articles in an hour cause one login attempt and each gets the same why — and an article asked for after 6 hours tries once more
- [ ] After a login page that did not answer, the wait is 15 minutes, not 6 hours
- [ ] A page that still shows the paywall after a successful login answers the `paywall` why, and does not log in again
- [ ] A 403 never leads to a login attempt
- [ ] Through `news_article` over MCP, five De Tijd stories failing for one reason put exactly one line in Slack, naming De Tijd and containing neither the email nor the password
- [ ] Each outcome of the login is decided by a function tested against recorded login pages; the captcha page is made up from Auth0's documented markers and its fixture says so
- [ ] Harry's own login code logs in against the real page from the built image, starting with an empty session directory (live)

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

