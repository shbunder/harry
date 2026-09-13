---
name: icloud_list_events
namespace: icloud
description: The events on one day, from the calendar
requires: [icloud]
always_load: false
annotations:
  readOnlyHint: true
enabled: true
---

Returns the day's events with their times and titles. Depends on the iCloud connector, so
when that has no credential this tool is not offered rather than offered and broken.
