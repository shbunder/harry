"""An alert sink that writes to a file, so what Harry sent can be read back."""

from pathlib import Path

from harry.sdk import Context, Registry

HEARD = 'heard.txt'


class Notebook:
    def __init__(self, folder: Path) -> None:
        self._path = folder / HEARD

    def write_down(self, message: str) -> None:
        with self._path.open('a', encoding='utf-8') as handle:
            handle.write(message + '\n')


def register(registry: Registry, context: Context) -> None:
    notebook = Notebook(context.folder)
    registry.connector(notebook)
    registry.alerts(notebook.write_down)
