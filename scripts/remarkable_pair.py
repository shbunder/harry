"""Exchange a one-time code for a reMarkable device token, once per machine.

    make remarkable-pair CODE=abcd1234

The code comes from my.remarkable.com/device/desktop/connect and expires in a few minutes,
so fetch it and use it in the same sitting.

**The token is written, never printed.** It grants complete read and write access to every
document on the tablet with no scopes, so it goes straight into the gitignored `.env.local`
beside the connector and nowhere else — not to stdout, not to a log, not into `~/.rmapi`,
which remarkapy would use by default and which the NUC's container cannot read.

This is a one-shot command rather than something the connector does, because pairing is
interactive by nature: somebody has to be at a browser. A connector that could pair itself
would be a connector that could be talked into pairing at 06:30.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from remarkapy import Client, RemarkableAPIError

WHERE = Path('.harry/connectors/remarkable/.env.local')
KEY = 'DEVICE_TOKEN'


def pair(code: str, where: Path = WHERE, register=None) -> Path:
    """Swap the code for a token and write it. Returns the file it wrote."""
    token = (register or _register)(code.strip())
    if not token:
        raise SystemExit('the tablet returned no token, which should not happen — try a fresh code')
    _write(where, token)
    return where


def _register(code: str) -> str:
    """remarkapy does the exchange. `persist_config` stays off so `~/.rmapi` is not written."""
    client = Client(interactive=False, persist_config=False)
    try:
        return client.register_device(code)
    except RemarkableAPIError as error:
        # Never the response body: a rejected pairing echoes the request, and the request
        # carried the code.
        raise SystemExit(
            f'the code was refused — get another from my.remarkable.com/device/desktop/connect ({type(error).__name__})'
        ) from error
    finally:
        client.close()


def _write(where: Path, token: str) -> None:
    """Set one key, leaving anything else in the file alone."""
    where.parent.mkdir(parents=True, exist_ok=True)
    lines = where.read_text(encoding='utf-8').splitlines() if where.is_file() else []
    kept = [line for line in lines if not line.strip().startswith(f'{KEY}=')]
    where.write_text('\n'.join([*kept, f'{KEY}={token}']).strip() + '\n', encoding='utf-8')


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or '').splitlines()[0])
    parser.add_argument('code', help='the 8 characters from my.remarkable.com/device/desktop/connect')
    parser.add_argument('--to', type=Path, default=WHERE, help=f'where to write it (default: {WHERE})')
    asked = parser.parse_args(argv)

    written = pair(asked.code, asked.to)
    print(f'✓ paired. The device token is in {written}, which is gitignored.')
    print('  Nothing else to do — start Harry and the remarkable connector will load.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
