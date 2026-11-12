"""`python -m app.launch`: what this process runs is chosen by HERD_ROLE.

- `api`: bootstrap (organisation and first owner, if nobody exists), then the public
  and the internal app, two uvicorn servers in one event loop.
- `migrate`: `alembic upgrade head`, then exit (the cluster's one-off job).
- `all`: migrate first, then as `api` (single container, docker compose).

SIGTERM and SIGINT stop both servers in an orderly way; if one server ends (for
example because its port is taken), the other is stopped too.
"""

import asyncio
import signal
import sys
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Literal, Protocol

import uvicorn
from fastapi import FastAPI

from app.core.config import Settings, get_settings
from app.core.db import get_database
from app.core.logging import configure_logging
from app.core.migrations import upgrade_head
from app.modules.orgs.service import ensure_bootstrap
from app.web.internal import create_internal_app
from app.web.public import create_public_app

Step = Literal["migrate", "serve"]

_STEPS: dict[str, tuple[Step, ...]] = {
    "api": ("serve",),
    "migrate": ("migrate",),
    "all": ("migrate", "serve"),
}


class Server(Protocol):
    should_exit: bool

    async def serve(self) -> None: ...


class _Server(uvicorn.Server):
    """A uvicorn server that leaves signal handling to `run_servers`.

    Each uvicorn.Server installs its own SIGTERM handler; with two of them the second
    replaces the first, and only one server would ever hear the signal.
    """

    @contextmanager
    def capture_signals(self) -> Iterator[None]:
        yield


def steps_for(role: str) -> tuple[Step, ...]:
    return _STEPS[role]


def _config(app: FastAPI, port: int) -> uvicorn.Config:
    # 0.0.0.0: the process runs in a container; which ports are reachable is decided there.
    # access_log off and log_config None: RequestLogMiddleware writes the request line and
    # uvicorn's own loggers propagate to the root handler set up by configure_logging.
    return uvicorn.Config(
        app,
        host="0.0.0.0",  # noqa: S104
        port=port,
        access_log=False,
        log_config=None,
        server_header=False,
    )


def server_configs(settings: Settings) -> tuple[uvicorn.Config, uvicorn.Config]:
    return (
        _config(create_public_app(), settings.public_port),
        _config(create_internal_app(), settings.internal_port),
    )


async def _serve(server: Server) -> int:
    """Run one server; its exit code. Uvicorn calls sys.exit(1) when it cannot start, and
    a SystemExit escaping a task would tear down the loop before the other server stops."""
    try:
        await server.serve()
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 1
    return 0


async def run_servers(servers: Sequence[Server]) -> int:
    """Serve until a signal arrives or one server ends; then stop all. The exit code."""

    def stop() -> None:
        for server in servers:
            server.should_exit = True

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop)
    tasks = [asyncio.create_task(_serve(server)) for server in servers]
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        stop()
        return max(await asyncio.gather(*tasks))
    finally:
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.remove_signal_handler(sig)


async def bootstrap(settings: Settings) -> None:
    """The organisation and first owner, in their own transaction, before serving."""
    async with get_database().session_factory() as session:
        await ensure_bootstrap(session, settings)
        await session.commit()


async def serve(settings: Settings) -> int:
    await bootstrap(settings)
    return await run_servers([_Server(config) for config in server_configs(settings)])


def main() -> None:
    settings = get_settings()
    configure_logging(settings)
    for step in steps_for(settings.role):
        if step == "migrate":
            upgrade_head()
        elif code := asyncio.run(serve(settings)):
            sys.exit(code)


if __name__ == "__main__":
    main()
