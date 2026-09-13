"""Records each run in a file beside itself, so a test can see that it ran."""

from harry.sdk import Context, Registry

RAN = 'ran.txt'


def register(registry: Registry, context: Context) -> None:
    @registry.job
    def ticker() -> None:
        with (context.folder / RAN).open('a', encoding='utf-8') as handle:
            handle.write('tick\n')
