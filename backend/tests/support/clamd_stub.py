"""A local clamd for tests (plan M9 task 18, J11: ClamAV only as a stub here).

It speaks clamd's `zINSTREAM` over TCP as clamd does: chunks, each with a 4-byte
big-endian length, until a chunk of length 0; then one reply ending in NUL:
`stream: OK`, or `stream: Eicar-Test-Signature FOUND` when the stream holds the EICAR
test string. Scriptable through `mode`: `ok` (judge the content), `error` (an ERROR
reply, as clamd sends over its StreamMaxLength), `hang` (read everything, never
answer) and `close` (hang up without a reply). `received` counts the streams it read.
Runs on 127.0.0.1 in the test's event loop (`start`, `stop`)."""

import asyncio
from dataclasses import dataclass, field

# The EICAR anti-virus test file (harmless by definition), in two pieces so this
# source file is not itself a match for a scanner.
EICAR = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-" + b"STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"


@dataclass
class ClamdStub:
    mode: str = "ok"
    received: int = 0
    _server: asyncio.Server | None = field(default=None, repr=False)

    @property
    def address(self) -> str:
        assert self._server is not None
        host, port = self._server.sockets[0].getsockname()[:2]
        return f"{host}:{port}"

    async def start(self) -> "ClamdStub":
        self._server = await asyncio.start_server(self._serve, "127.0.0.1", 0)
        return self

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            self._server.close_clients()  # a `hang` connection would keep wait_closed waiting
            await self._server.wait_closed()

    async def _serve(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            command = await reader.readuntil(b"\0")
            if command != b"zINSTREAM\0":
                writer.write(b"UNKNOWN COMMAND\0")
                return
            data = bytearray()
            while length := int.from_bytes(await reader.readexactly(4), "big"):
                data += await reader.readexactly(length)
            self.received += 1
            if self.mode == "hang":
                await asyncio.sleep(3600)
            if self.mode == "close":
                return
            if self.mode == "error":
                writer.write(b"INSTREAM size limit exceeded. ERROR\0")
            elif EICAR in data:
                writer.write(b"stream: Eicar-Test-Signature FOUND\0")
            else:
                writer.write(b"stream: OK\0")
            await writer.drain()
        except (asyncio.IncompleteReadError, ConnectionError):
            return
        finally:
            writer.close()
