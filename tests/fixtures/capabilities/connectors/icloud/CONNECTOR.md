---
name: icloud
description: Calendar and reminders, over CalDAV
expires: manual
enabled: true
config:
  app_password:
    description: An app-specific password from appleid.apple.com
    secret: true
    required: true
---

Nothing sets `app_password` in the tests that use this, which is the point: a connector
with no credential disables itself and says which one.
