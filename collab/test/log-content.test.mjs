// No page text in any log line (review M2 U10): a state the schema does not allow was
// logged with ProseMirror's message, which quotes the content (`<"Passwort …">`).
import { afterEach, test } from "node:test";
import assert from "node:assert/strict";
import * as Y from "yjs";
import { editorProblem } from "../markdown.mjs";
import { createCollabServer } from "../server.mjs";
import { liveFixture, synced, until } from "./helpers.mjs";

let live;

afterEach(async () => {
  await live?.stop();
  live = null;
});

const SECRET = "Passwort des Tresors: hunter2";

test("a schema problem names the node, not its text", () => {
  const problem = editorProblem({
    type: "doc",
    content: [
      {
        type: "heading",
        attrs: { level: 1 },
        content: [{ type: "text", text: SECRET }, { type: "hardBreak" }],
      },
    ],
  });
  assert.ok(problem !== null);
  assert.match(problem, /heading/);
  assert.ok(!problem.includes("hunter2"), problem);
});

test("a refused save logs no page text", async () => {
  const lines = [];
  live = await liveFixture({
    markdown: "Start",
    createCollabServer,
    checkWorkers: 0,
    log: (message, fields) => lines.push(JSON.stringify({ message, ...fields })),
  });
  const anna = live.open({ cookie: "herd_session=token-a" });
  await synced(anna);
  // What only a non-browser client sends: a hard break in a heading.
  const heading = new Y.XmlElement("heading");
  heading.setAttribute("level", 1);
  heading.insert(0, [new Y.XmlText(SECRET), new Y.XmlElement("hardBreak")]);
  anna.doc.getXmlFragment("default").push([heading]);
  await until(() => live.api.unrepresentable >= 1);
  assert.ok(lines.some((line) => line.includes("live save refused")));
  for (const line of lines) assert.ok(!line.includes("hunter2"), line);
});
