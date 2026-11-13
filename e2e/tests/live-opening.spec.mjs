// Opening a page in the live editor writes nothing (review M2, invariant C): every
// sample the live editor opens (the wiki pages of `collab/test/corpus/` and the samples
// of `collab/test/constructs.mjs`) is opened in Chromium, synced and left with "Fertig"
// without typing; the stored Markdown is byte-identical and no version is written.
import { readFileSync, readdirSync } from "node:fs";
import { expect, test } from "@playwright/test";
import { liveDocument } from "../../collab/markdown.mjs";
import { meaningOf } from "../../collab/meaning.mjs";
import { CONSTRUCTS, IMAGES_IN_TEXT, REPORTED } from "../../collab/test/constructs.mjs";
import { OWNER, call, pageUrl, publishedPage, signIn, teamSpace } from "./helpers.mjs";

const CORPUS = new URL("../../collab/test/corpus/", import.meta.url);

/** Words the page view shows (text, link targets, image sources and alt texts). */
function wordsOf(tree, out = new Set()) {
  for (const key of ["value", "url", "alt"]) {
    const value = String(tree[key] ?? "").replace(/wiki:[^)\s]*/g, ""); // the title is the text
    for (const word of value.match(/[\p{L}\d]{2,}/gu) ?? []) out.add(word);
  }
  for (const child of tree.children ?? []) wordsOf(child, out);
  return out;
}

function samples() {
  const out = readdirSync(CORPUS)
    .filter((file) => file.endsWith(".md"))
    .map((file) => [file, readFileSync(new URL(file, CORPUS), "utf8")]);
  for (const group of [CONSTRUCTS, IMAGES_IN_TEXT, REPORTED]) {
    for (const [name, value] of Object.entries(group)) {
      out.push([name, typeof value === "string" ? value : value.markdown]);
    }
  }
  return out.filter(([, markdown]) => liveDocument(markdown).safe);
}

test("opening a page in the live editor and leaving changes nothing", async ({ browser }) => {
  test.setTimeout(600_000);
  const context = await browser.newContext();
  await signIn(context, OWNER);
  const space = await teamSpace(context, "Öffnen");
  const all = samples();
  expect(all.length).toBeGreaterThan(90);
  const tab = await context.newPage();
  const changed = [];
  for (const [index, [name, markdown]] of all.entries()) {
    const doc = await publishedPage(context, space.id, `Probe ${index}`, markdown);
    const versions = await call(context, "GET", `/api/pages/${doc.id}/versions?limit=100`);
    await tab.goto(pageUrl(space, doc, "live"));
    const editor = tab.getByRole("textbox", { name: `Inhalt von „Probe ${index}“` });
    await expect(editor).toHaveAttribute("contenteditable", "true");
    await expect(tab.getByRole("status")).toHaveText("Synchronisiert");
    // The document's content is shown (the test cannot pass on an empty page).
    for (const word of [...wordsOf(meaningOf(markdown))].slice(0, 3)) {
      if ((await editor.textContent()).includes(word)) continue;
      // A word may be a link target or image source rather than text.
      expect(await editor.innerHTML(), `${name}: "${word}" not shown`).toContain(word);
    }
    // "Fertig" asks the server to store everything now: anything the browser changed
    // in the shared document would be saved here.
    await tab.getByRole("button", { name: "Fertig" }).click();
    await expect(tab).toHaveURL(new RegExp(`/p/${doc.path}$`));
    const stored = await call(context, "GET", `/api/pages/${doc.id}`);
    const after = await call(context, "GET", `/api/pages/${doc.id}/versions?limit=100`);
    if (stored.content_md !== markdown || stored.version !== doc.version) changed.push(name);
    if (after.items.length !== versions.items.length) changed.push(`${name} (version)`);
  }
  expect(changed).toEqual([]);
  await context.close();
});
