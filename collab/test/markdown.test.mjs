// Markdown <-> Yjs (plan M2 task 9): every supported construct survives a round trip
// and is stable after one pass; what the editor cannot show survives as a raw block.
import { test } from "node:test";
import assert from "node:assert/strict";
import * as Y from "yjs";
import { markdownToYDoc, yDocToMarkdown, RAW_LANGUAGE, FIELD } from "../markdown.mjs";

const roundTrip = (md) => yDocToMarkdown(markdownToYDoc(md));

const FIXTURES = {
  headings: "# Eins\n\n## Zwei\n\n###### Sechs",
  paragraphs: "Erster Absatz.\n\nZweiter Absatz.",
  marks: "Text mit **fett**, _kursiv_, ~~durch~~ und `code`.",
  links: '[Seite](https://example.com "Titel") und [relativ](/spaces/x/p/a) und <mailto:a@b.de>',
  images: "![Logo](/api/attachments/01a1d2d9-2de5-75db-9dc6-a6fa1307273d?inline=1)",
  lists: "- a\n- b\n  - c\n\n1. eins\n2. zwei",
  tasks: "- [ ] offen\n- [x] erledigt",
  quotes: "> Zitat\n> zweite Zeile",
  code: "```python\nprint(1)\n```",
  tables: "| a | b |\n| --- | --- |\n| 1 | 2 |",
  rules: "oben\n\n---\n\nunten",
  breaks: "Zeile eins  \nZeile zwei",
  escapes: "\\*kein fett\\* und 2 \\< 3",
  umlauts: "Grüße, Ärger, Öl, Straße – „Zitat“",
};

for (const [name, md] of Object.entries(FIXTURES)) {
  test(`round trip: ${name}`, () => {
    const once = roundTrip(md);
    assert.equal(roundTrip(once), once, "stable after one pass");
    // Nothing of the text is lost on the way.
    for (const word of md.match(/[\p{L}\d]{2,}/gu) ?? []) {
      assert.ok(once.includes(word), `${word} missing in ${JSON.stringify(once)}`);
    }
  });
}

test("simple constructs come back as written", () => {
  for (const name of ["headings", "paragraphs", "marks", "lists", "tasks", "code", "rules"]) {
    assert.equal(roundTrip(FIXTURES[name]), FIXTURES[name], name);
  }
});

test("wiki links come back as written, and code is left alone", () => {
  const md = "Siehe [[Urlaub]] und [[Neue Seite]], aber \\[nicht\\].";
  assert.equal(roundTrip(md), md);
  const code = "```\n\\[\\[bleibt\\]\\]\n```";
  assert.equal(roundTrip(code), code);
});

test("the document lives in the editor's field", () => {
  const doc = markdownToYDoc("# Hallo");
  assert.ok(doc.getXmlFragment(FIELD).length > 0);
});

const UNSUPPORTED = {
  "html block": '<div class="x">roh</div>',
  "inline html": "Text mit <b>fett</b> darin",
  "html comment": "<!-- Notiz -->",
  "reference link": "Siehe [die Seite][ref].\n\n[ref]: https://example.com",
  footnote: "Satz mit Fußnote[^1].\n\n[^1]: Die Fußnote.",
  "fence in raw": "<details>\n\n```\ncode\n```\n\n</details>",
  // The page view does not show these images (review M2 T11): neither does the editor.
  "image from a blob": "Screenshot: ![eins](blob:https://app.example/1) und mehr",
  "image from a file": "![zwei](file:///C:/bild.png)",
  "image from data": "![drei](data:image/png;base64,iVBORw0KGgo=)",
};

for (const [name, md] of Object.entries(UNSUPPORTED)) {
  test(`unsupported syntax survives as raw block: ${name}`, () => {
    const doc = markdownToYDoc(`# Vorher\n\n${md}\n\nNachher.`);
    const json = JSON.stringify(doc.getXmlFragment(FIELD).toJSON());
    assert.ok(json.includes(RAW_LANGUAGE), "kept as a raw block in the editor");
    const out = yDocToMarkdown(doc);
    assert.equal(out, `# Vorher\n\n${md}\n\nNachher.`);
    assert.equal(roundTrip(out), out);
  });
}

test("an empty page stays empty", () => {
  assert.equal(roundTrip(""), "");
});

test("a document edited like a browser would is converted back", () => {
  const doc = markdownToYDoc("Hallo");
  const other = new Y.Doc();
  Y.applyUpdate(other, Y.encodeStateAsUpdate(doc));
  const paragraph = other.getXmlFragment(FIELD).get(0);
  paragraph.get(0).insert(5, " Welt");
  assert.equal(yDocToMarkdown(other), "Hallo Welt");
});
