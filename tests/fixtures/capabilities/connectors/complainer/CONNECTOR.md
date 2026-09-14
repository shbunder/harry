---
name: complainer
description: Reports its own failure through context.alert, the way a real connector does
expires: manual
enabled: true
config:
  token:
    description: A credential it will put in its own alert message, as people do
    secret: true
    required: true
---

The half of alerting that was missing. A connector that knows its credential has lapsed
says so, rather than logging it where nobody is looking.
