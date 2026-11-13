// Live editing never changes what a page means (review M2 R1): every sample, converted
// into the editor's document and back, reads the same to the page view's parser, and
// a second conversion changes nothing more. Samples: CommonMark and GFM constructs,
// the cases the review found, wiki pages (`corpus/`) and this repository's own docs.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { yDocToProsemirrorJSON } from "y-prosemirror";
import {
  FIELD,
  editorProblem,
  jsonToMarkdown,
  jsonToYDoc,
  liveDocument,
  RAW_LANGUAGE,
} from "../markdown.mjs";
import { difference, meaningOf, sameMeaning } from "../meaning.mjs";
import { CONSTRUCTS, IMAGES_IN_TEXT, REPORTED } from "./constructs.mjs";

const here = (path) => fileURLToPath(new URL(path, import.meta.url));

/** Every word the page view shows (text, link targets, image sources and alt texts). */
function wordsOf(tree, out = new Set()) {
  for (const key of ["value", "url", "alt"]) {
    const value = String(tree[key] ?? "").replace(/wiki:[^)\s]*/g, ""); // the title is the text
    for (const word of value.match(/[\p{L}\d]{2,}/gu) ?? []) out.add(word);
  }
  for (const child of tree.children ?? []) wordsOf(child, out);
  return out;
}

/** The Markdown a live session saves for the page (after one edit anywhere), the way
 * the browser gets it: through the Y.Doc, valid for the editor's schema (review M2 S1,
 * S8), and with everything the page shows still in the document. */
function liveSave(markdown) {
  const document = liveDocument(markdown);
  assert.ok(document.safe, "opened for live editing");
  assert.equal(editorProblem(document.json), null, "valid for the browser's editor");
  const json = yDocToProsemirrorJSON(jsonToYDoc(document.json), FIELD);
  const content = JSON.stringify(json);
  for (const word of wordsOf(meaningOf(markdown))) {
    assert.ok(content.includes(word), `"${word}" missing from the editor's document`);
  }
  return { markdown: jsonToMarkdown(json), json };
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

for (const [name, markdown] of Object.entries(IMAGES_IN_TEXT)) {
  test(`an image next to text stays rich text and unchanged (review S1): ${name}`, () => {
    assertKeepsMeaning(name, markdown);
    const { json } = liveSave(markdown);
    assert.equal(rawBlocks(json), 0, "edited as rich text");
    assert.ok(JSON.stringify(json).includes('"image"'));
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

test("two lists in a row stay two lists", () => {
  // The second list takes the other marker, so they are not joined into one.
  for (const markdown of ["- eins\n\n* zwei", "1. eins\n\n1) zwei"]) {
    assertKeepsMeaning(markdown, markdown);
  }
});

test("marks around each other keep their meaning in any order", () => {
  const samples = ["~~**x**~~ und ***y*** und _~~z~~_", " 0. ~~**x**~~\n\n       )"];
  for (const markdown of [
    ...samples,
    "[**a**](b) und **[a](b)** und _www.g_",
    "- _-\\\n  ._\n\n* ;",
  ]) {
    assertKeepsMeaning(markdown, markdown);
    assert.equal(rawBlocks(liveSave(markdown).json), 0, markdown);
  }
});

test("a raw block keeps the indentation of its first line", () => {
  const markdown = " 0. <b>x</b>\n\n       )";
  assertKeepsMeaning(markdown, markdown);
  assert.equal(liveSave(markdown).markdown, markdown);
});

test("a table is read the way the page view reads it", () => {
  // A `|` inside code ends the cell for the page view; the editor reads it the same way
  // (one parser for both), so the table is rich text and keeps its meaning.
  const markdown = "Text\n\n| A | B |\n|---|---|\n| x | `a|b` |\n\nEnde";
  assertKeepsMeaning("table", markdown);
  assert.equal(rawBlocks(liveSave(markdown).json), 0);
});

test("the comparison sees what the page view sees", () => {
  assert.ok(sameMeaning("* a\n* b", "- a\n- b"));
  assert.ok(sameMeaning("| a |\n|---|\n| 1 |", "| a   |\n| --- |\n| 1   |"));
  assert.ok(sameMeaning("Titel\n=====", "# Titel"));
  assert.ok(sameMeaning("&copy; 2026", "© 2026"));
  assert.ok(!sameMeaning("&copy;", "&amp;copy;"));
  assert.ok(!sameMeaning("\\# kein Titel", "# kein Titel"));
  assert.ok(sameMeaning("[[API_Keys]]", "[[API\\_Keys]]"), "wiki links by their title");
  assert.ok(!sameMeaning("[[A]]", "\\[\\[A\\]\\]"), "an escaped wiki link is text");
  assert.ok(!sameMeaning("`[[A]]`", "`[A](wiki:A)`"), "no wiki links in code");
  assert.ok(!sameMeaning("[a](<b c>)", "[a](b c)"));
  assert.ok(!sameMeaning("[![a](x.png)](https://example.org)", "![a](x.png)"));
});
