# reMarkable fixtures

## Recorded, on 14 September 2026

| File | What it is |
|---|---|
| `folder-listing.json` | What `remarkapy.Client.list_directory_hydrated()` really returns for a folder, taken from a live tablet. Two of the entries; nothing else changed |

**`lastModified` is the reason this file exists.** It is epoch milliseconds in a string —
`"1789384626339"` — and the connector's stand-in originally used ISO 8601, which nothing on
the wire ever sends. Sorting by it still worked, by luck, because 13-digit strings compare
in the right order; the timestamp Claude was shown was simply wrong. A hand-written
stand-in cannot catch that, and a recording can.

The document ids and hashes are real. They belong to a test page pushed by
`make test-live` and carry nothing private.
