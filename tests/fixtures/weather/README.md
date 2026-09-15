# Recorded Open-Meteo answers

Real responses, saved on the day they were fetched. **No weather test reaches
api.open-meteo.com** — see `.claude/rules/external-sources.md`.

| File | What it is | What it proves |
|---|---|---|
| `leuven-today.json` | A real answer for Leuven, daily block only | The happy path for the day: word, high, low, rain chance |
| `leuven-no-today.json` | The same answer with its daily arrays emptied | A 200 with nothing in it is unavailable, not a crash |
| `leuven-unknown-code.json` | The same answer with a WMO code the table does not carry | The numbers still print; no word is invented |
| `leuven-hourly.json` | A real answer with `hourly=temperature_2m`, 15 September 2026 | The hourly strip: 24 readings, 17 of them between 06:00 and 22:00 |

`leuven-today.json` has no `hourly` block, which is why it is also the fixture for *the
service answered the day but not the hours*.
