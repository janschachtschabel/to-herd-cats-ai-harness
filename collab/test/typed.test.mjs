// What people type in the live editor is stored as Markdown that reads back as what
// they see (review M2 S2, S3): each case starts from the editor's document, as the
// browser builds it, and passes the save check (`readback.mjs`), which also makes sure
// the page opens in the live editor again.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readBack } from "../readback.mjs";

const text = (value, ...marks) => ({
  type: "text",
  text: value,
  ...(marks.length && { marks: marks.map((type) => (typeof type === "string" ? { type } : type)) }),
});
const paragraph = (...content) => ({ type: "paragraph", content });
const doc = (...content) => ({ type: "doc", content });
const item = (...content) => ({ type: "listItem", content });
const code = (value, language = "bash") => ({
  type: "codeBlock",
  attrs: { language },
  content: [text(value)],
});
const link = (href) => ({ type: "link", attrs: { href } });

const CASES = {
  "bold and italic overlapping": [
    doc(
      paragraph(text("fett ", "bold"), text("beides", "bold", "italic"), text(" kursiv", "italic")),
    ),
    "**fett _beides_** _kursiv_",
  ],
  "bold ending in punctuation before a letter": [
    doc(paragraph(text("Hinweis:", "bold"), text("Text"))),
    "**Hinweis:**&#x54;ext",
  ],
  "bold inside a word": [
    doc(paragraph(text("Haupt", "bold"), text("bahnhof"))),
    "**Haupt**bahnhof",
  ],
  "a paragraph typed with leading spaces": [
    doc(paragraph(text("    eingerückt und\tTab"))),
    "eingerückt und Tab",
  ],
  "an address with underscores typed as text": [
    doc(paragraph(text("https://example.org/mein_pfad_x"))),
    "https\\://example.org/mein_pfad_x",
  ],
  "an address the editor linked": [
    doc(paragraph(text("https://example.org/a_b", link("https://example.org/a_b")))),
    "<https://example.org/a_b>",
  ],
  "an e-mail address": [
    doc(paragraph(text("Mail an anna@example.org bitte"))),
    "Mail an anna\\@example.org bitte",
  ],
  "a list of code blocks": [
    doc({
      type: "orderedList",
      attrs: { start: 1 },
      content: [item(paragraph(), code("npm ci")), item(paragraph(), code("npm test"))],
    }),
    "1. ```bash\n   npm ci\n   ```\n2. ```bash\n   npm test\n   ```",
  ],
  "an image inside a sentence": [
    doc(
      paragraph(
        text("Klicke auf "),
        { type: "image", attrs: { src: "/icons/save.png", alt: "Speichern", title: null } },
        text(" und dann auf Fertig."),
      ),
    ),
    "Klicke auf ![Speichern](/icons/save.png) und dann auf Fertig.",
  ],
  "a wiki link with emphasis characters": [
    doc(paragraph(text("Siehe [[API_Keys]] und [[a *b*]]."))),
    "Siehe [[API_Keys]] und [[a \\*b\\*]].",
  ],
  "an emoji right after bold punctuation": [
    doc(paragraph(text("Achtung!", "bold"), text("\u{1F600} ok"))),
    "**Achtung!**&#x1F600; ok",
  ],
  "an exclamation mark before a wiki link": [doc(paragraph(text("![[Seite]]"))), "\\![[Seite]]"],
  "a rule as the first thing in a list item": [
    doc({ type: "bulletList", content: [item(paragraph(), { type: "horizontalRule" })] }),
    "- ___",
  ],
  "a wiki link before a parenthesis": [doc(paragraph(text("[[Seite]](x)"))), "[[Seite]]\\(x)"],
  "a link in a table whose address holds a pipe": [
    doc({
      type: "table",
      content: [
        {
          type: "tableRow",
          content: [
            {
              type: "tableHeader",
              attrs: { align: null },
              content: [{ type: "tableParagraph", content: [text("a", link("/x?a|b"))] }],
            },
          ],
        },
      ],
    }),
    "| [a](/x?a\\|b) |\n| --- |",
  ],
  "delimiters on both sides of a referenced character": [
    doc(paragraph(text("e"), text("a", "bold"), text("(", "bold", "strike"))),
    "&#x65;**&#x61;~~(~~**",
  ],
  "a table cell with a pipe": [
    doc({
      type: "table",
      content: [
        {
          type: "tableRow",
          content: [
            {
              type: "tableHeader",
              attrs: { align: null },
              content: [{ type: "tableParagraph", content: [text("a|b")] }],
            },
          ],
        },
      ],
    }),
    "| a\\|b |\n| --- |",
  ],
};

for (const [name, [json, markdown]] of Object.entries(CASES)) {
  test(`typed content reads back as typed: ${name}`, () => {
    const result = readBack(json);
    assert.equal(result.markdown, markdown);
    assert.ok(result.ok, result.problem);
  });
}

test("code with a backslash before a pipe in a table cell is refused, never stored", () => {
  // GFM reads `\|` in a cell as an escaped pipe and `\\|` as the end of the cell: no
  // Markdown says this, so the save check refuses it (and the editor shows a notice).
  const cell = (content) => ({
    type: "tableHeader",
    attrs: { align: null },
    content: [{ type: "tableParagraph", content }],
  });
  const json = doc({
    type: "table",
    content: [{ type: "tableRow", content: [cell([text("a\\|b", "code")])] }],
  });
  assert.equal(readBack(json).ok, false);
});
