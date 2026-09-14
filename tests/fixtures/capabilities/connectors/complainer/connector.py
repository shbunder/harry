"""Says something went wrong, and puts its own credential in the message doing it."""

from harry.sdk import Context, Registry


class Complainer:
    def __init__(self, context: Context) -> None:
        self._context = context

    def give_up(self) -> bool:
        return self._context.alert(
            f'the service rejected {self._context.config["token"]}',
            key='rejected',
        )


def register(registry: Registry, context: Context) -> None:
    registry.connector(Complainer(context))
