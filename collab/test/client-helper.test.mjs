// The test client behaves like a browser when it is destroyed while connecting: a
// browser's WebSocket closes quietly then, Node's `ws` raised an uncaught error, which
// failed the integration test whenever its cleanup met a reconnect attempt.
import { createServer } from "node:http";
import { test } from "node:test";
import assert from "node:assert/strict";
import { client } from "./helpers.mjs";

test("a client destroyed while its connection is being set up raises nothing", async () => {
  const server = createServer();
  const pending = [];
  server.on("upgrade", (_request, socket) => pending.push(socket)); // never answered
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const uncaught = [];
  const record = (error) => uncaught.push(error.message);
  process.on("uncaughtException", record);
  try {
    const c = client(`ws://127.0.0.1:${server.address().port}`, { grant: "herd_cg_a" });
    while (pending.length === 0) await new Promise((resolve) => setImmediate(resolve));
    c.destroy();
    await new Promise((resolve) => setTimeout(resolve, 100));
    assert.deepEqual(uncaught, []);
  } finally {
    process.off("uncaughtException", record);
    for (const socket of pending) socket.destroy();
    await new Promise((resolve) => server.close(resolve));
  }
});
