"""`python -m app.launch`: what this process runs is chosen by HERD_ROLE.

- `api`: bootstrap (organisation and first owner, if nobody exists), then the public
  and the internal app, two uvicorn servers in one event loop.
- `migrate`: `alembic upgrade head`, then exit (the cluster's one-off job).
- `all`: migrate first, then as `api` (single container, docker compose), and, when
  HERD_INTERNAL_TOKEN is set, the collab process (`node collab/server.mjs`) as a child
  on 127.0.0.1:HERD_COLLAB_PORT. If the child ends, the launcher stops and exits 3.
- `collab`: the collab process alone, in place of the launcher (its own deployment).
- `worker`: the outbox dispatcher (`app.worker`) and the internal port only (probes,
  metrics); `all` runs the worker next to the API, in the same event loop.

SIGTERM and SIGINT stop every server in an orderly way (the worker finishes the batch
in progress); if one ends (for example because its port is taken), the others are
stopped too.
"""

import asyncio
import logging
import os
import signal
import socket
import sys
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from typing import Literal, Protocol

import uvicorn
from fastapi import FastAPI
from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.config import Settings, get_settings
from app.core.db import get_database
from app.core.logging import configure_logging
from app.core.migrations import upgrade_head
from app.core.spool import remove_stale_spools
from app.modules.messaging.live import LiveHub
from app.modules.orgs.service import ensure_bootstrap
from app.web.collab_proxy import MAX_MESSAGE_BYTES
from app.web.internal import create_internal_app
from app.web.public import create_public_app
from app.worker.main import Worker, create_worker

logger = logging.getLogger(__name__)

Step = Literal["migrate", "serve", "collab"]

_STEPS: dict[str, tuple[Step, ...]] = {
    "api": ("serve",),
    "migrate": ("migrate",),
    "all": ("migrate", "serve"),
    "collab": ("collab",),
    "worker": ("serve",),
}

COLLAB_EXIT_CODE = 3
COLLAB_STOP_SECONDS = 15.0
# How long an idle keep-alive connection stays open (HERD_KEEP_ALIVE_SECONDS). A client
# that reuses a pooled connection at the moment the server closes it gets the request
# reset (ECONNRESET; a reverse proxy answers 502 to a POST). Uvicorn's 5 s are shorter
# than the pools in front of it (nginx upstream and ALB 60 s, Traefik 90 s, Caddy
# 120 s): the server must be the side that outlasts them, so that the client always
# closes first. A proxy that keeps its upstream connections longer (Google's load
# balancers 600 s, an ALB set higher) needs a longer value (review M4-1 P14).
DEFAULT_KEEP_ALIVE_SECONDS = 150
KEEP_ALIVE_BOUNDS = (5, 3600)


class _KeepAlive(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="HERD_", env_file=".env", extra="ignore")

    keep_alive_seconds: int = Field(
        default=DEFAULT_KEEP_ALIVE_SECONDS, ge=KEEP_ALIVE_BOUNDS[0], le=KEEP_ALIVE_BOUNDS[1]
    )


def keep_alive_seconds() -> int:
    """HERD_KEEP_ALIVE_SECONDS, within KEEP_ALIVE_BOUNDS; otherwise a start-up error."""
    try:
        return _KeepAlive().keep_alive_seconds
    except ValidationError:
        low, high = KEEP_ALIVE_BOUNDS
        raise ValueError(
            f"HERD_KEEP_ALIVE_SECONDS must be a whole number of seconds from {low} to {high}"
        ) from None


class Server(Protocol):
    should_exit: bool

    async def serve(self) -> None: ...


class _Server(uvicorn.Server):
    """A uvicorn server that leaves signal handling to `run_servers`.

    Each uvicorn.Server installs its own SIGTERM handler; with two of them the second
    replaces the first, and only one server would ever hear the signal.

    `before_shutdown` runs when the server begins to stop: uvicorn waits for open
    responses to finish, and live streams (`/api/stream`) never do unless told to.
    """

    def __init__(
        self, config: uvicorn.Config, before_shutdown: Callable[[], None] | None = None
    ) -> None:
        super().__init__(config)
        self.before_shutdown = before_shutdown

    @contextmanager
    def capture_signals(self) -> Iterator[None]:
        yield

    async def shutdown(self, sockets: list[socket.socket] | None = None) -> None:
        if self.before_shutdown is not None:
            self.before_shutdown()
        await super().shutdown(sockets)


def _closing_streams(app: object) -> Callable[[], None] | None:
    """What ends the live streams of the public app `app` (its hub), if it has one."""
    hub = getattr(getattr(app, "state", None), "live", None)
    return hub.close_all if isinstance(hub, LiveHub) else None


def steps_for(role: str) -> tuple[Step, ...]:
    return _STEPS[role]


def _config(
    app: FastAPI, port: int, forwarded_allow_ips: str | None, keep_alive: int
) -> uvicorn.Config:
    # 0.0.0.0: the process runs in a container; which ports are reachable is decided there.
    # access_log off and log_config None: RequestLogMiddleware writes the request line and
    # uvicorn's own loggers propagate to the root handler set up by configure_logging.
    # Forwarded headers (client IP for audit and rate limits, https scheme for cookies)
    # are believed only from `forwarded_allow_ips`, and only where it is given.
    return uvicorn.Config(
        app,
        host="0.0.0.0",  # noqa: S104
        port=port,
        access_log=False,
        log_config=None,
        server_header=False,
        proxy_headers=forwarded_allow_ips is not None,
        forwarded_allow_ips=forwarded_allow_ips,
        timeout_keep_alive=keep_alive,
        ws_max_size=MAX_MESSAGE_BYTES,  # live editing (/collab): what the collab process takes
    )


def server_configs(
    settings: Settings, worker: Worker | None = None
) -> tuple[uvicorn.Config, uvicorn.Config]:
    """The public server sits behind the reverse proxy; the internal one is reached
    directly (probes, scrapes) and believes no forwarded headers."""
    keep_alive = keep_alive_seconds()
    return (
        _config(
            create_public_app(), settings.public_port, settings.forwarded_allow_ips, keep_alive
        ),
        _config(create_internal_app(worker=worker), settings.internal_port, None, keep_alive),
    )


def internal_config(settings: Settings, worker: Worker) -> uvicorn.Config:
    """The internal server alone (role worker)."""
    return _config(
        create_internal_app(worker=worker), settings.internal_port, None, keep_alive_seconds()
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


# What the collab process may see of this environment (review M2 R13): the system's
# basics, Node's own settings and its own settings, never the database credentials or
# any other secret of the API.
_COLLAB_PASSED = frozenset({"PATH", "HOME", "LANG", "LC_ALL", "TZ"})
_COLLAB_PREFIXES = ("NODE_", "HERD_COLLAB_")


def collab_env(settings: Settings, *, host: str) -> dict[str, str]:
    """The collab process's environment: an allow list of this one, plus what it must
    agree on with the API (values from a .env file reach it only this way)."""
    env = {
        name: value
        for name, value in os.environ.items()
        if name in _COLLAB_PASSED or name.startswith(_COLLAB_PREFIXES)
    }
    env.update(
        HERD_ROLE=settings.role,
        HERD_COLLAB_HOST=host,
        HERD_COLLAB_PORT=str(settings.collab_port),
        HERD_COLLAB_API_URL=settings.collab_api_url or f"http://127.0.0.1:{settings.internal_port}",
        HERD_SESSION_COOKIE_NAME=settings.session_cookie_name,
    )
    if settings.internal_token is not None:
        env["HERD_INTERNAL_TOKEN"] = settings.internal_token.get_secret_value()
    if settings.public_url:
        env["HERD_PUBLIC_URL"] = settings.public_url
    return env


def collab_command(settings: Settings) -> list[str]:
    return ["node", str(settings.collab_script)]


class CollabProcess:
    """The collab process as a child, driven like the uvicorn servers: `serve` runs
    it until it ends; setting `should_exit` sends SIGTERM (it saves what is unsaved
    and closes), SIGKILL after COLLAB_STOP_SECONDS. Ending on its own is exit 3."""

    def __init__(self, command: Sequence[str], env: Mapping[str, str]) -> None:
        self.command = list(command)
        self.env = dict(env)
        self._process: asyncio.subprocess.Process | None = None
        self._stopping = False

    @property
    def returncode(self) -> int | None:
        return self._process.returncode if self._process else None

    @property
    def should_exit(self) -> bool:
        return self._stopping

    @should_exit.setter
    def should_exit(self, value: bool) -> None:
        if value and not self._stopping:
            self._stopping = True
            self._terminate()

    def _terminate(self) -> None:
        process = self._process
        if process is None or process.returncode is not None:
            return
        process.terminate()
        asyncio.get_running_loop().call_later(COLLAB_STOP_SECONDS, self._kill, process)

    @staticmethod
    def _kill(process: asyncio.subprocess.Process) -> None:
        if process.returncode is None:
            process.kill()

    async def serve(self) -> None:
        if self._stopping:
            return
        try:
            self._process = await asyncio.create_subprocess_exec(*self.command, env=self.env)
        except OSError as exc:
            logger.error("collab process cannot start", extra={"error": type(exc).__name__})
            raise SystemExit(COLLAB_EXIT_CODE) from None
        if self._stopping:  # asked to stop while it was starting
            self._terminate()
        code = await self._process.wait()
        if not self._stopping:
            logger.error("collab process ended", extra={"code": code})
            raise SystemExit(COLLAB_EXIT_CODE)


def run_collab(settings: Settings) -> None:
    """Role `collab`: node replaces this process (tini forwards signals to it)."""
    command = collab_command(settings)
    os.execvpe(command[0], command, collab_env(settings, host="0.0.0.0"))  # noqa: S104, S606


async def bootstrap(settings: Settings) -> None:
    """The organisation and first owner, in their own transaction, before serving."""
    async with get_database().session_factory() as session:
        await ensure_bootstrap(session, settings)
        await session.commit()


async def serve(settings: Settings) -> int:
    if settings.role == "worker":
        alone = create_worker(get_database())
        return await run_servers([_Server(internal_config(settings, alone)), alone])
    remove_stale_spools(settings.data_dir)
    await bootstrap(settings)
    worker = create_worker(get_database()) if settings.role == "all" else None
    servers: list[Server] = [
        _Server(config, before_shutdown=_closing_streams(config.app))
        for config in server_configs(settings, worker)
    ]
    if worker is not None:
        servers.append(worker)
    if settings.role == "all":
        if settings.internal_token is None:
            logger.warning("live editing off: HERD_INTERNAL_TOKEN is not set")
        else:
            env = collab_env(settings, host="127.0.0.1")
            servers.append(CollabProcess(collab_command(settings), env))
    return await run_servers(servers)


def main() -> None:
    settings = get_settings()
    configure_logging(settings)
    for step in steps_for(settings.role):
        if step == "migrate":
            upgrade_head()
        elif step == "collab":
            run_collab(settings)
        elif code := asyncio.run(serve(settings)):
            sys.exit(code)


if __name__ == "__main__":
    main()
