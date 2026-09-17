# De Tijd fixtures

What the tijd connector's rules are tested against. No test here reaches tijd.be.

**The repository is on GitHub, so nothing here is a paid article or an account's details.**
Pages a subscriber saw are reduced to the markup the rules read, with placeholder prose.

## Recorded, on 16 September 2026, from Harry's image

| File | What it is | What was changed |
|---|---|---|
| `article-logged-out.html` | `tijd.be/r/t/1/id/10686286`, followed to the article, in a headed Chromium with no session. `<html class="paywall-active">`; 263 characters of prose through trafilatura | The contents of every `<script>`, `<style>` and `<svg>` removed — 860 KB to 105 KB. The markup and the teaser are as served |
| `login-refused.html` | `auth.mediafin.be/u/login/password` after one deliberately wrong password: `#error-element-password` with `data-error-code="wrong-email-credentials"` and "E-mailadres of wachtwoord onjuist" | Every script and style emptied, **except one line kept on purpose**: the page's own JavaScript reads `getAttribute("data-captcha-provider")`. The real page mentions "captcha" 77 times with no captcha shown, and a rule that matched the word would call every refusal a captcha. Every `value=""` emptied, the `state` token and any email address replaced |

`news/tijd-nieuws.xml`, beside the other feeds, is `www.tijd.be/rss/nieuws.xml` from the same day:
RSS 2.0, 10 items, each link a redirect stub, no pictures. Nothing changed.

## Derived from those, by hand

| File | What it is | Why it is not recorded |
|---|---|---|
| `article-logged-in.html` | `article-logged-out.html` with `<html lang="nl" class="">` — the class a logged-in subscriber was served, measured the same day — and eight placeholder paragraphs after the teaser, in the same `ac_paragraph` markup. 2,639 characters of prose | The recorded page carried a paid article and the account's details |
| `login-unexpected.html` | `login-refused.html` with the error element taken out: a password page that neither finished nor refused, as a page asking for a one-time code would look to the rules | Nobody has seen De Tijd ask for a code |
| `login-captcha.html` | `login-unexpected.html` with a captcha element in Auth0's documented shape: `data-captcha-provider`, `data-captcha-sitekey`, `ulp-auth0-v2-captcha`. **Made up.** The attribute names are the ones the recorded page's own script looks for | Nobody has seen De Tijd show a captcha, and one cannot be asked for |
