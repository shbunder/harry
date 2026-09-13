"""Everything a capability may import — and the only thing it may.

    from harry.sdk import Context, Registry

    def register(registry: Registry, context: Context) -> None:
        ...

A capability never imports `harry.scheduler`, `harry.store`, `harry.mcp` or `harry.main`.
`harry.boundary` reads a capability's imports before running it and the loader skips one
that reaches past this module, so the rule holds without anybody remembering it.

**Why it holds the whole design up.** The day the scheduler is replaced, the thing that
must not break is every capability sitting on disk — including the ones a third party
wrote, which nobody here can grep. They cannot break if none of them ever named it.

**Why this module has no code of its own.** Anything with behaviour here is behaviour
every capability depends on, which is the opposite of what the SDK is for. When a
capability needs something core has, it gets added here by name, deliberately, in a
change somebody reviews — rather than reached for sideways through `harry.store`.

It imports from `harry.config` and `harry.registry` and nothing else, and nothing under
`.harry/` in either direction. An SDK that imports a capability is a core that knows a
capability's name.
"""

# No `from __future__ import annotations` here, on purpose: it would put a fourth public
# name in this module's namespace, and the test that this module is exactly three names is
# worth more than the line it costs. There is nothing here to annotate.

from harry.config import Principal
from harry.registry import Context, Registry

__all__ = ['Context', 'Principal', 'Registry']
