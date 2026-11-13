// The pages of the "opening a page changes nothing" browser test (review M2 3, ruling C):
// - repo: this repository's own Markdown files (`git ls-files`),
// - hostile: hand-written hostile and sloppy pages (`fixtures/hostile.mjs`),
// - targeted: first blocks ending in a file or domain name, uneven tables, a pipe in
//   code in a table (`fixtures/targeted.json`),
// - constructs: the collab process's samples (`collab/test/constructs.mjs`, corpus),
// - mutated: sections of the repository's files with 1–3 mutations (CRLF, tabs,
//   trailing spaces, quotes and lists around them, joined lines, images, entities, ...),
// - editor: documents the live editor itself stores (generated, written by the save
//   check),
// - files named in HERD_E2E_PAGE_FILES (comma-separated JSON files of `{ name, md }`,
//   optionally `group`) for a longer local run.
// Seeded, so a run can be repeated. HERD_E2E_MUTATED and HERD_E2E_GENERATED set how many
// mutated and generated pages (defaults: the CI subset); HERD_E2E_GROUPS (comma-separated)
// keeps only those groups (`file` keeps every page of the files).
import { execFileSync } from "node:child_process";
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { CONSTRUCTS, IMAGES_IN_TEXT, REPORTED } from "../collab/test/constructs.mjs";
import { generateDocument, seeded } from "../collab/test/generate.mjs";
import { readBack } from "../collab/readback.mjs";
import { HOSTILE } from "./fixtures/hostile.mjs";

const ROOT = new URL("..", import.meta.url).pathname;
const CORPUS = join(ROOT, "collab", "test", "corpus");

function repo() {
  const files = execFileSync("git", ["ls-files", "*.md"], { cwd: ROOT }).toString().split("\n");
  return files
    .filter(Boolean)
    .map((file) => ({ name: file, md: readFileSync(join(ROOT, file), "utf8") }));
}

function constructs() {
  const out = readdirSync(CORPUS)
    .filter((file) => file.endsWith(".md"))
    .map((file) => ({ name: file, md: readFileSync(join(CORPUS, file), "utf8") }));
  for (const group of [CONSTRUCTS, IMAGES_IN_TEXT, REPORTED]) {
    for (const [name, value] of Object.entries(group)) {
      out.push({ name, md: typeof value === "string" ? value : value.markdown });
    }
  }
  return out;
}

/** Sections of a document: split before level 1–3 headings outside code fences. */
function sections(markdown) {
  const out = [];
  let current = [];
  let fence = false;
  for (const line of markdown.split("\n")) {
    if (/^\s*(```|~~~)/.test(line)) fence = !fence;
    if (!fence && /^#{1,3} /.test(line) && current.length > 8) {
      out.push(current.join("\n"));
      current = [];
    }
    current.push(line);
  }
  if (current.length) out.push(current.join("\n"));
  return out;
}

function mutations(r) {
  const p = (x) => r.next() < x;
  return {
    crlf: (s) => s.replace(/\n/g, "\r\n"),
    tabs: (s) => s.replace(/^( {2,4})/gm, "\t"),
    trailing: (s) => s.replace(/$/gm, () => (p(0.3) ? "  " : p(0.2) ? " " : "")),
    zeroWidth: (s) => s.replace(/ /g, () => (p(0.03) ? " ​" : " ")),
    star: (s) => s.replace(/^(\s*)- /gm, "$1* "),
    markers: (s) => s.replace(/^(\s*)- /gm, (_, a) => `${a}${r.pick(["-", "*", "+"])} `),
    quote: (s) =>
      s
        .split("\n")
        .map((l) => `> ${l}`)
        .join("\n"),
    list: (s) =>
      `- ${s
        .split("\n")
        .map((l, i) => (i ? `  ${l}` : l))
        .join("\n")}`,
    ordered: (s) =>
      `1. ${s
        .split("\n")
        .map((l, i) => (i ? `   ${l}` : l))
        .join("\n")}`,
    indent: (s) => s.replace(/^(?=\S)/gm, () => " ".repeat(r.int(0, 3))),
    join: (s) => s.replace(/\n\n/g, () => (p(0.4) ? "\n" : "\n\n")),
    blank: (s) => s.replace(/\n\n/g, () => (p(0.3) ? "\n\n\n\n" : "\n\n")),
    nbsp: (s) => s.replace(/ /g, () => (p(0.02) ? " " : " ")),
    image: (s) => s.replace(/\. /g, () => (p(0.15) ? ". ![icon](/i/x.png) " : ". ")),
    wiki: (s) => s.replace(/ ([A-ZÄÖÜ][a-zäöü]{4,}) /g, (m, w) => (p(0.1) ? ` [[${w}]] ` : m)),
    entity: (s) => s.replace(/&/g, "&amp;").replace(/ü/g, "&uuml;"),
    noEnd: (s) => s.replace(/\n+$/, ""),
    swap: (s) => {
      const lines = s.split("\n");
      for (let i = 0; i < 3 && lines.length > 3; i++) {
        const a = r.int(0, lines.length - 1);
        const b = r.int(0, lines.length - 1);
        [lines[a], lines[b]] = [lines[b], lines[a]];
      }
      return lines.join("\n");
    },
    cut: (s) => {
      const at = r.int(0, s.length);
      return s.slice(0, at) + s.slice(at + r.int(0, 20));
    },
    setext: (s) =>
      s
        .replace(/^# (.+)$/gm, (_, t) => `${t}\n${"=".repeat(t.length)}`)
        .replace(/^## (.+)$/gm, (_, t) => `${t}\n---`),
  };
}

export function mutated(base, count, seed = 20261113) {
  const r = seeded(seed);
  const ops = mutations(r);
  const names = Object.keys(ops);
  const pool = base.flatMap((doc) =>
    sections(doc.md)
      .filter((s) => s.length > 200 && s.length < 6000)
      .map((md) => ({ name: doc.name, md })),
  );
  return Array.from({ length: count }, (_, i) => {
    const section = r.pick(pool);
    const applied = Array.from({ length: r.int(1, 3) }, () => r.pick(names));
    const md = applied.reduce((text, op) => ops[op](text), section.md);
    return { name: `${section.name}#${i}[${applied.join("+")}]`, md };
  });
}

/** Documents the live editor stores: generated editor documents, written by the save
 * check (those it would refuse are not stored, so they are left out). */
export function editorStored(count, seed = 20261114) {
  const r = seeded(seed);
  const out = [];
  for (let i = 0; out.length < count && i < count * 4; i++) {
    const written = readBack(generateDocument(r));
    if (written.ok) out.push({ name: `generated ${i}`, md: written.markdown });
  }
  return out;
}

/** All pages: `{ group, name, md }`. */
export function pages({
  mutatedCount = Number(process.env.HERD_E2E_MUTATED ?? 60),
  generatedCount = Number(process.env.HERD_E2E_GENERATED ?? 40),
  files = (process.env.HERD_E2E_PAGE_FILES ?? "").split(",").filter(Boolean),
  only = (process.env.HERD_E2E_GROUPS ?? "").split(",").filter(Boolean),
} = {}) {
  const own = repo();
  const targeted = JSON.parse(readFileSync(new URL("./fixtures/targeted.json", import.meta.url)));
  const groups = {
    repo: own,
    hostile: Object.entries(HOSTILE).map(([name, md]) => ({ name, md })),
    targeted,
    constructs: constructs(),
    mutated: mutated(own, mutatedCount),
    editor: editorStored(generatedCount),
  };
  const out = Object.entries(groups).flatMap(([group, list]) =>
    list.map((page) => ({ group, ...page })),
  );
  for (const file of files) {
    for (const page of JSON.parse(readFileSync(file, "utf8"))) {
      out.push({ name: page.name, md: page.md, group: `file:${page.group ?? "page"}` });
    }
  }
  const kept = (group) => only.some((name) => group === name || group.startsWith(`${name}:`));
  return only.length ? out.filter((page) => kept(page.group)) : out;
}
