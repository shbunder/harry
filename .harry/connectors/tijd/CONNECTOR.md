---
name: tijd
description: De Tijd's articles, read the way a subscriber reads them — in a logged-in browser
provides: []
expires: session
enabled: true
config:
  email:
    description: The email address the De Tijd subscription signs in with. An account that signs in with Google or Apple has no password Harry can use.
    required: true
    secret: true
  password:
    description: That account's De Tijd password. Used only when the saved session has lapsed, and never twice within 6 hours after De Tijd refuses it — De Tijd blocks an account after repeated failures.
    required: true
    secret: true
  session_dir:
    description: Where the logged-in session is saved. Keep it on the data volume and nowhere else — the file is a working De Tijd login for anyone who has it.
    default: /data/tijd
  browser_endpoint:
    description: 'The browser container to read through, as ws://harry-browser:3000/. Empty means Harry starts a browser of its own, which is what a laptop does. The real stack sets it in docker-compose.yml, because it is deployment rather than a credential.'
    default: ""
---

De Tijd's articles, in full, read the way a subscriber reads them: in a real browser window,
logged in. The news connector reads De Tijd's feed like any other and hands every article
link on tijd.be to this connector. **Harry logs in by itself** whenever the saved session has
lapsed, so nobody renews anything while the password is right.

**What Harry sends:** nothing, in the normal case. When it cannot read an article, one line
in Slack says why — once per reason per 24 hours — and the story prints the feed's own
summary instead.

## Setting it up

1. **An account that signs in with an email and a password.** One that signs in with Google or
   Apple has no password Harry can type.
2. **Put the login beside this file**, readable only by you:

   ```bash
   install -m 600 /dev/null .harry/connectors/tijd/.env.local
   $EDITOR .harry/connectors/tijd/.env.local
   ```

   ```ini
   EMAIL=you@example.com
   PASSWORD=…
   ```

3. **Add De Tijd's feed to the news connector**, in `.harry/connectors/news/.env.local`. `FEEDS`
   is one setting, so it names every feed, not only the new one:

   ```ini
   FEEDS=vrt=VRT NWS=https://www.vrt.be/vrtnws/nl.rss.articles.xml|bbc=BBC News=https://feeds.bbci.co.uk/news/rss.xml|tijd=De Tijd=https://www.tijd.be/rss/nieuws.xml
   ```

4. **Restart Harry**, and check it loaded: `docker compose restart harry`, then
   `make health | grep -A1 tijd`.

The first De Tijd article Harry is asked for logs in. The session is saved to
`/data/tijd/storage-state.json` on the data volume, mode 600, and reused from then on. The
log says `logged in to De Tijd`, and on every later login, how many days the previous session
lasted.

## Where the browser runs

**In its own container**, `harry-browser`, on the real stack. It renders De Tijd's pages and the
advertising scripts on them, so it is the one container here that meets hostile input — and it is
given nothing: no connector's `.env.local`, no root `.env.local`, no data volume, no published
port. It runs as an unprivileged user with every Linux capability dropped and **Chromium's own
sandbox on**. An exploited renderer lands somewhere empty.

Harry connects to it and states what the browser must be — headed, full Chromium, sandboxed — on
every connect. A browser container asked for nothing launches headless, and De Tijd answers 403.

The session stays Harry's: it is read from `/data/tijd` on Harry's side and handed to the browser
for the call, never written inside the browser container.

**With `BROWSER_ENDPOINT` empty, Harry starts a browser itself**, in its own container. That is
what a laptop does and what `make test-live` does. It runs unsandboxed there, because Chromium's
sandbox needs Docker's syscall filtering relaxed, and relaxing it where the credentials are is
what the separate container avoids.

When the browser container is down, De Tijd's stories print their summary and Slack gets the
usual `the browser … could not start` line. Nothing else changes.

## How it reads a page

1. It opens the article in a **headed Chromium** — a real browser window, drawn on the virtual
   display the image starts. De Tijd refuses every headless browser: measured on 2026-09-16,
   `chrome-headless-shell` and full Chromium headless both got `403 Blocked`, headed got 200.
2. A page served with `<html class="paywall-active">` is behind the paywall. Harry logs in —
   on `https://www.tijd.be/`, because on an article a subscription dialog covers the Log in
   button — and opens the article again.
3. After every page read in full, it saves the session again, so the cookies De Tijd renews
   are kept.

One article at a time. The browser is started for each article and closed after it.

## When it goes wrong

| What reaches Slack | What happened | What to do |
|---|---|---|
| `De Tijd: Harry could not log in: De Tijd refused the email or password in .harry/connectors/tijd/.env.local…` | The login service said the email or password is wrong | Check both in `.env.local`, then restart Harry. **Harry does not try again for 6 hours**, because De Tijd blocks an account after repeated failures — a restart is how a corrected password takes effect at once |
| `…the login page asked for a check Harry cannot answer, such as a captcha…` | De Tijd showed a captcha | Nothing Harry can do. If it keeps happening, full text needs a person to log in by hand, which is a change to this connector |
| `…at the email step, the login page did not show what Harry expects in time…` (or another step before the password) | A field Harry fills in did not come in time, or the Log in click led somewhere that is not `auth.mediafin.be` — where Harry types nothing | Usually a slow page, and Harry tries again in 15 minutes. If it keeps saying so, De Tijd changed its login page; the step named is where to start looking, in `pages.py` |
| `…after the password was sent, the login page did not show what Harry expects…` | The password went in, and the page neither came back to De Tijd nor refused it — most likely a new step, such as a one-time code | A person has to look. No new login for 6 hours |
| `…De Tijd's homepage did not answer. Harry tries again in 15 minutes` | The network, or De Tijd, was down | Usually nothing. Nothing was refused, so the wait is short |
| `De Tijd: De Tijd refused the browser (403)…` | De Tijd's bot filter turned the browser away | **Not the login** — logging in again will not help. The filter has tightened before; see how it reads a page, above |
| `De Tijd: the browser Harry reads De Tijd with could not start, or stopped` | Chromium would not start, most often because there is no display — `make serve` on a machine without one | In the container the image starts the display, and `make logs` says `with-display: Xvfb did not start` if it could not. Outside the container, this connector cannot work |
| `De Tijd: the article page did not load within 30 seconds, or could not be reached` | Slow or down | Usually transient |
| `De Tijd: De Tijd answered 404 for the article` | The article is gone | Nothing |
| `De Tijd: Harry logged in, but De Tijd still shows the paywall…` | The login worked and the article is still withheld | Check the subscription. No new login for 6 hours |
| `De Tijd: Harry could not save the De Tijd session in /data/tijd…` | The data volume is full or not writable | Fix the volume. Until then every article logs in again |
| `De Tijd: reading the article took longer than 150 seconds…` | Something inside the browser never came back | Usually transient. The morning page moved on with the summary |
| `De Tijd: an earlier De Tijd article is still stuck in the browser…` | The read above has still not come back, and holds the browser | If it repeats, restart Harry |
| `…the browser or the network failed at the email step. Nothing was refused…` (or another step, or `after De Tijd took the password`) | Chromium or the connection gave out part-way through the login, before the password was sent or after De Tijd had already taken it | Usually transient. Harry tries again in 15 minutes |
| `…the browser or the network failed after the password was sent…` | The same, between the password's click and the page coming back to De Tijd — so nobody can tell whether De Tijd counted it | No new login for 6 hours, in case it was a refusal |

**Every line is a fixed sentence.** None carries the email, the password, an error's text or
a URL. The same reason twice in a day is one line; a different reason is a second line.

**A saved session that is not a session** — cut short by a full disk, edited by hand, or one
the browser refuses after an upgrade — is set aside with a line in the log, and Harry logs in
afresh.

**No read takes longer than 150 seconds.** Starting the browser, two pages of 30 seconds and
a login of 60 are the waits Harry sets, and they add up to that. The limit catches everything
else — a page wedged in an ad script — and the story prints its summary.

**After a failure that cost time, De Tijd rests for 10 minutes.** A page that did not load, a
read that got stuck, or a browser that would not run: every De Tijd article in the next 10
minutes gets the same answer at once, without the browser. The morning page reads all its
stories inside one tool call, and a client gives up on a call that stays silent for 300
seconds, so one slow failure has to cost one wait rather than one per story. Once a read is
known stuck, later articles are answered at once until it comes back or Harry restarts.

**What this does not cover:** a De Tijd that is slow but *succeeding* is never cut short, so a
morning page with many slow De Tijd stories can still outlast its client. Then the 07:00
watchdog says no page was built.

**Without this connector** — no `EMAIL` or `PASSWORD` — De Tijd's links are fetched like any
other page, De Tijd answers 403, and the news connector's own line says `De Tijd: De Tijd
answered 403`. The headlines are unaffected.

## What it holds

`PASSWORD` is the De Tijd account's password, and it can change the account and the
subscription as well as read articles. `EMAIL` and `PASSWORD` are declared secret, so every
line this connector sends has them scrubbed. The saved session in `/data/tijd` is a working
login for anyone who has the file.

This is personal use of a subscription you pay for, on your own device. Nothing here is shared
or redistributed.
