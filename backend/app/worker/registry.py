"""Which handler gets which events.

A module registers its handlers with the decorator:

    @handler("message", "notify_on_message")
    async def notify_on_message(session: AsyncSession, event: Event) -> None: ...

A handler gets every event whose type is one of its prefixes or starts with one of
them followed by a dot (`message` matches `message.created`, not `messages.x`). The
name is stored with each delivery and is a metric label: it never changes once an
event has been delivered under it, and it is unique.

Each handler works off a lane of its own; it runs in its lane's transaction (in a
savepoint per event, with the delivery record) and must be idempotent and never
commit: an event may reach a handler more than once, for example when an earlier
batch was rolled back.
"""

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import MAX_HANDLER_CHARS, Event

HandlerFunc = Callable[[AsyncSession, Event], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class Handler:
    name: str
    prefixes: tuple[str, ...]
    func: HandlerFunc

    def matches(self, event_type: str) -> bool:
        return any(event_type == p or event_type.startswith(f"{p}.") for p in self.prefixes)


class HandlerRegistry:
    def __init__(self) -> None:
        self._handlers: list[Handler] = []

    def handler(
        self, event_type_prefix: str | Sequence[str], name: str
    ) -> Callable[[HandlerFunc], HandlerFunc]:
        prefixes = (
            (event_type_prefix,) if isinstance(event_type_prefix, str) else tuple(event_type_prefix)
        )
        prefixes = tuple(p.rstrip(".") for p in prefixes)
        if not name or len(name) > MAX_HANDLER_CHARS or not all(prefixes) or not prefixes:
            raise ValueError(f"handler {name!r}: a name and at least one prefix are needed")
        if any(h.name == name for h in self._handlers):
            raise ValueError(f"handler {name!r} is registered twice")

        def _register(func: HandlerFunc) -> HandlerFunc:
            self._handlers.append(Handler(name, prefixes, func))
            return func

        return _register

    def handlers(self) -> list[Handler]:
        """Every handler (each has a lane of its own), in the order registered."""
        return list(self._handlers)

    def for_type(self, event_type: str) -> list[Handler]:
        """The handlers of `event_type`, in the order they were registered."""
        return [h for h in self._handlers if h.matches(event_type)]


# The registry of the running worker; modules register into it when imported, so the
# worker's entry point imports every module that has handlers.
REGISTRY = HandlerRegistry()
handler = REGISTRY.handler
