"""Harry — a companion service that does what Claude decides.

Claude thinks. Harry does. Harry holds the credentials, runs the browsers, renders the
documents, talks to the tablet and to Slack.

Everything Harry can do lives in `.harry/`, in three kinds: a **connector** is somewhere
Harry can reach, a **tool** is something Claude can ask for, a **job** is something Harry
does on its own. Core provides only the registry, the MCP server, the scheduler, the store
and the HTTP app.

Capabilities import from `harry.sdk`. They never reach into core directly — see
`.claude/rules/capability-shape.md`.
"""

from __future__ import annotations

__version__ = '0.1.0'

__all__ = ['__version__']
