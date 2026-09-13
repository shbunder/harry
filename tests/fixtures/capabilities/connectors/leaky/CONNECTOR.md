---
name: leaky
description: Raises with its own credential in the message
expires: manual
enabled: true
config:
  api_key:
    description: The credential this connector then puts in an exception, as people do
    secret: true
    required: true
---

The failure that matters for `/health`: nobody writes a careful exception message when
something has just gone wrong.
