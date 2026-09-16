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
| `…at the email step, the login page did not show what Harry expects…` (or another step) | A field Harry fills in was not there, or De Tijd added a step such as a one-time code | De Tijd changed its login page. The step named is where to start looking, in `pages.py` |
| `…De Tijd's homepage did not answer. Harry tries again in 15 minutes` | The network, or De Tijd, was down | Usually nothing. Nothing was refused, so the wait is short |
| `De Tijd: De Tijd refused the browser (403)…` | De Tijd's bot filter turned the browser away | **Not the login** — logging in again will not help. The filter has tightened before; see how it reads a page, above |
| `De Tijd: the browser Harry reads De Tijd with could not start, or stopped` | Chromium would not start, most often because there is no display — `make serve` on a machine without one | In the container the image starts the display. Outside it, this connector cannot work |
| `De Tijd: the article page did not load within 30 seconds, or could not be reached` | Slow or down | Usually transient |
| `De Tijd: De Tijd answered 404 for the article` | The article is gone | Nothing |
| `De Tijd: Harry logged in, but De Tijd still shows the paywall…` | The login worked and the article is still withheld | Check the subscription. No new login for 6 hours |
| `De Tijd: Harry could not save the De Tijd session in /data/tijd…` | The data volume is full or not writable | Fix the volume. Until then every article logs in again |

**Every line is a fixed sentence.** None carries the email, the password, an error's text or
a URL. The same reason twice in a day is one line; a different reason is a second line.

**A saved session that is not a session** — cut short by a full disk, edited by hand — is set
aside with a line in the log, and Harry logs in afresh.

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
