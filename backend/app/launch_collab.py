"""The collab process as the launcher drives it (`app.launch`): role `all` runs it as a
child on 127.0.0.1 (`CollabProcess`), role `collab` execs it in place of the launcher
(`run_collab`). Either way it sees only an allow list of this environment."""

import asyncio
import logging
import os
from collections.abc import Mapping, Sequence

from app.core.config import Settings

logger = logging.getLogger("app.launch")

COLLAB_EXIT_CODE = 3
COLLAB_STOP_SECONDS = 15.0

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
    )
    if settings.role == "all":
        # The one instance, as its child: reached on loopback only.
        env["HERD_COLLAB_ADVERTISE_URL"] = f"ws://127.0.0.1:{settings.collab_port}"
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
