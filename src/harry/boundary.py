"""May this capability's code be run at all?

A capability imports `harry.sdk` and nothing else under `harry` — the rule in
`.claude/rules/capability-shape.md`, checked here rather than only in review, because a
review catches it only if somebody is looking.

The check is **static**: the imports are read before the module is executed, so a
forbidden import never takes effect rather than being noticed once it has. It reads every
`.py` file in the folder, not only the entry module, because the import that reaches past
the SDK is usually in the client sitting beside it.

**What it cannot see**: `importlib.import_module('harry.store')`, or any other import
assembled at run time. That is a stated limit rather than an oversight. This is a boundary
for people writing capabilities, not a sandbox — a capability's code runs in Harry's
process with Harry's credentials, and nothing here changes that. What it buys is that the
rule fails at start-up, on the machine of whoever broke it, instead of at the review that
did not happen.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

SDK = 'harry.sdk'


def forbidden_imports(folder: Path) -> list[str]:
    """Every import in this folder that reaches past the SDK, as `file:line: name`.

    Empty means the folder is safe to run. A file that does not parse raises
    `SyntaxError`, which the loader treats like any other failure — it would have raised
    at import a moment later anyway, and the reason is the same either way.
    """
    findings: list[str] = []
    for path in sorted(folder.rglob('*.py')):
        tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            for name in _reaches_past_the_sdk(node):
                findings.append(f'{path.relative_to(folder)}:{node.lineno} imports {name}')
    return findings


def _reaches_past_the_sdk(node: ast.Import | ast.ImportFrom) -> Iterator[str]:
    """The names one import statement pulls in that a capability may not have."""
    if isinstance(node, ast.Import):
        for alias in node.names:
            if _is_core(alias.name):
                yield alias.name
    elif isinstance(node, ast.ImportFrom):
        # A relative import is inside the capability's own folder. Every file in there is
        # read by the loop above, so the rule still covers whatever it reaches.
        if node.level:
            return
        module = node.module or ''
        if module == 'harry':
            # `from harry import sdk` is the allowed spelling; `from harry import store`
            # is the same reach as `import harry.store` wearing different clothes.
            for alias in node.names:
                if alias.name != 'sdk':
                    yield f'harry.{alias.name}'
        elif _is_core(module):
            yield module


def _is_core(name: str) -> bool:
    """True for anything under `harry` that is not the SDK.

    `import harry` on its own counts: the package is the door to everything behind it,
    and a capability has no reason to open it.
    """
    return name == 'harry' or (name.startswith('harry.') and name != SDK and not name.startswith(f'{SDK}.'))
