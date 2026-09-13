---
name: morning-page
description: The day's weather, agenda and a few full articles, on the tablet by 07:00
trigger: claude
deadline: "07:00"
timezone: Europe/Brussels
enabled: true
---

Ask Harry for today's candidates. Read the headlines and pick the six to eight that
matter, write a two-sentence intro in your own words, then call `digest_build` with your
picks.

When the page is on the tablet, call `harry_mark_done("morning-page")`. Harry has no other
way of knowing you were here, and without it you will get a "has not run today" message
about a page you are holding.
