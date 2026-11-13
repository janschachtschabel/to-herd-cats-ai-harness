// Live editing never changes what a page means (review M2 R1): every sample, converted
// into the editor's document and back, reads the same to the page view's parser, and
// a second conversion changes nothing more. Samples: CommonMark and GFM constructs,
// the cases the review found, wiki pages (`corpus/`) and this repository's own docs.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { jsonToMarkdown, liveDocument, RAW_LANGUAGE } from "../markdown.mjs";
import { difference, meaningOf, sameMeaning } from "../meaning.mjs";
import { CONSTRUCTS, REPORTED } from "./constructs.mjs";

const here = (path) => fileURLToPath(new URL(path, import.meta.url));

/** The Markdown a live session saves for the page (after one edit anywhere). */
function liveSave(markdown) {
  const document = liveDocument(markdown);
  assert.ok(document.safe, "opened for live editing");
  return { markdown: jsonToMarkdown(document.json), json: document.json };
}

function assertKeepsMeaning(name, markdown) {
  const once = liveSave(markdown).markdown;
  const where = difference(meaningOf(markdown), meaningOf(once));
  assert.equal(where, null, `${name}: meaning changed at ${where}: ${JSON.stringify(once)}`);
  const twice = liveSave(once).markdown;
  assert.equal(twice, once, `${name}: a second live save changes the Markdown again`);
}

const rawBlocks = (json) => JSON.stringify(json).split(RAW_LANGUAGE).length - 1;

for (const [name, markdown] of Object.entries(CONSTRUCTS)) {
  test(`round trip keeps the meaning: ${name}`, () => assertKeepsMeaning(name, markdown));
}

for (const [name, { markdown, editable }] of Object.entries(REPORTED)) {
  test(`round trip keeps the meaning (review R1): ${name}`, () => {
    assertKeepsMeaning(name, markdown);
    const { json } = liveSave(markdown);
    assert.equal(rawBlocks(json) === 0, editable, editable ? "editable" : "kept as raw block");
  });
}

const corpus = readdirSync(here("./corpus/")).filter((file) => file.endsWith(".md"));
const docs = ["../../README.md", "../../docs/WIKI.md", "../../docs/STECKBRIEF.md"].concat(
  "../../docs/superpowers/specs/2026-11-12-to-herd-cats-ai-design.md",
);

for (const file of corpus) {
  test(`wiki page keeps its meaning and stays editable: ${file}`, () => {
    const markdown = readFileSync(here(`./corpus/${file}`), "utf8");
    assertKeepsMeaning(file, markdown);
  });
}

test("the wiki pages are edited as rich text, not raw blocks", () => {
  for (const file of ["onboarding.md", "it-handbuch.md", "protokoll.md"]) {
    const { json } = liveSave(readFileSync(here(`./corpus/${file}`), "utf8"));
    assert.equal(rawBlocks(json), 0, file);
  }
});

for (const path of docs) {
  test(`repository document keeps its meaning: ${path.split("/").pop()}`, () => {
    assertKeepsMeaning(path, readFileSync(here(path), "utf8"));
  });
}

test("a page whose blocks change meaning only together is not opened", () => {
  // Two bullet lists (different markers) come back as one list.
  const markdown = "- eins\n\n* zwei";
  assert.equal(liveDocument(markdown).safe, false);
  assert.equal(liveDocument("- eins\n\n- zwei").safe, true);
});

test("a block the editor would change is kept as a raw block", () => {
  // marked and the page view disagree on this table (a `|` inside code ends the cell
  // for the page view): written back unchanged.
  const markdown = "Text\n\n| A | B |\n|---|---|\n| x | `a|b` |\n\nEnde";
  const { markdown: out, json } = liveSave(markdown);
  assert.equal(rawBlocks(json), 1);
  assert.equal(out, markdown);
});

test("the comparison sees what the page view sees", () => {
  assert.ok(sameMeaning("* a\n* b", "- a\n- b"));
  assert.ok(sameMeaning("| a |\n|---|\n| 1 |", "| a   |\n| --- |\n| 1   |"));
  assert.ok(sameMeaning("Titel\n=====", "# Titel"));
  assert.ok(sameMeaning("&copy; 2026", "© 2026"));
  assert.ok(!sameMeaning("&copy;", "&amp;copy;"));
  assert.ok(!sameMeaning("\\# kein Titel", "# kein Titel"));
  assert.ok(!sameMeaning("[[API_Keys]]", "[[API\\_Keys]]"), "wiki links by their written title");
  assert.ok(!sameMeaning("[a](<b c>)", "[a](b c)"));
  assert.ok(!sameMeaning("[![a](x.png)](https://example.org)", "![a](x.png)"));
});
