// Typing in the live editor without timing (review M2 U8): every step waits for a
// concrete state of the editor (its ProseMirror selection, its status, the server's
// confirmation), never for a while. The editor takes over a clicked selection a few
// milliseconds after the click; keys pressed before then acted on the old one.
import { expect, test } from "@playwright/test";
import { OWNER, call, pageUrl, publishedPage, signIn, teamSpace } from "./helpers.mjs";

/** Where the live editor's selection is: the text of its text block, the caret's offset
 * in it and the block's size, whether it is at the document's end, and focus. */
function caret() {
  const editor = document.querySelector(".ProseMirror")?.editor;
  if (!editor) return null;
  const { selection, doc } = editor.state;
  const { $from } = selection;
  return {
    text: $from.parent.textContent,
    offset: $from.parentOffset,
    size: $from.parent.content.size,
    atEnd: selection.empty && selection.constructor.atEnd(doc).from === selection.from,
    focused: editor.view.hasFocus(),
  };
}

/** Waits until the editor's caret matches `wanted` (a subset of `caret()`). */
export async function caretIs(tab, wanted) {
  await expect
    .poll(async () => {
      const now = await tab.evaluate(caret);
      return now && Object.entries(wanted).every(([key, value]) => now[key] === value);
    })
    .toBe(true);
}

/** Clicks the text and waits until the editor's caret is in its block. */
export async function clickInto(tab, editor, text, block = text) {
  await editor.getByText(text, { exact: true }).click();
  await caretIs(tab, { text: block, focused: true });
}

/** The caret to the end of its block, confirmed by the editor. */
export async function toEndOfBlock(tab) {
  await tab.keyboard.press("End");
  await expect
    .poll(async () =>
      tab.evaluate(() => {
        const { $from } = document.querySelector(".ProseMirror").editor.state.selection;
        return $from.parentOffset === $from.parent.content.size;
      }),
    )
    .toBe(true);
}

/** The cursor at the end of the document, in a new paragraph. */
export async function newLineAtEnd(tab, editor) {
  await editor.click();
  await tab.keyboard.press("Control+End");
  await caretIs(tab, { atEnd: true, focused: true });
  await tab.keyboard.press("Enter");
  await caretIs(tab, { atEnd: true, size: 0 });
}

/** Opens a live page and waits until it is synced and editable. */
export async function openLive(tab, space, doc, title) {
  await tab.goto(pageUrl(space, doc, "live"));
  const editor = tab.getByRole("textbox", { name: `Inhalt von „${title}“` });
  await expect(editor).toHaveAttribute("contenteditable", "true");
  // The editor's own status (while the page loads, its skeletons are status regions too).
  const status = tab.getByRole("region", { name: title }).getByRole("status");
  await expect(status).toHaveText("Synchronisiert");
  return { editor, status };
}

/** A serial group of typing cases in a team space of their own: `typeAndSave(title,
 * markdown, type)` opens the page live, lets `type` act in the editor, saves with
 * "Fertig" and reloads the page view; it returns the tab, the page view's article and
 * the stored Markdown. */
export function typingCases(spaceName) {
  const shared = { context: null, space: null };
  test.describe.configure({ mode: "serial" });
  test.beforeAll(async ({ browser }) => {
    shared.context = await browser.newContext();
    await signIn(shared.context, OWNER);
    shared.space = await teamSpace(shared.context, spaceName);
  });
  test.afterAll(async () => {
    await shared.context?.close();
  });

  async function typeAndSave(title, markdown, type) {
    const doc = await publishedPage(shared.context, shared.space.id, title, markdown);
    const tab = await shared.context.newPage();
    const { editor } = await openLive(tab, shared.space, doc, title);
    await type(tab, editor);
    await tab.getByRole("button", { name: "Fertig" }).click();
    await expect(tab).toHaveURL(new RegExp(`/p/${doc.path}$`));
    await tab.reload();
    const stored = await call(shared.context, "GET", `/api/pages/${doc.id}`);
    const article = tab.getByRole("main").locator(".wiki-prose");
    return { tab, article, stored: stored.content_md };
  }

  return { shared, typeAndSave };
}
