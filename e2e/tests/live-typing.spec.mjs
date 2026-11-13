// What people type in the live editor is what the page shows afterwards (review M2 S2,
// S3): each case is typed in Chromium, saved with "Fertig", and the page view checked
// after a reload.
import { expect, test } from "@playwright/test";
import { OWNER, call, pageUrl, publishedPage, signIn, teamSpace } from "./helpers.mjs";

test.describe.configure({ mode: "serial" });

let context;
let space;

test.beforeAll(async ({ browser }) => {
  context = await browser.newContext();
  await signIn(context, OWNER);
  space = await teamSpace(context, "Tippen");
});

test.afterAll(async () => {
  await context?.close();
});

/** Opens the page live, lets `type` act in the editor, saves with "Fertig" and reloads
 * the page view; returns the browser tab and the stored Markdown. */
async function typeAndSave(title, markdown, type) {
  const doc = await publishedPage(context, space.id, title, markdown);
  const tab = await context.newPage();
  await tab.goto(pageUrl(space, doc, "live"));
  const editor = tab.getByRole("textbox", { name: `Inhalt von „${title}“` });
  await expect(editor).toHaveAttribute("contenteditable", "true");
  await expect(tab.getByRole("status")).toHaveText("Synchronisiert");
  await type(tab, editor);
  await tab.getByRole("button", { name: "Fertig" }).click();
  await expect(tab).toHaveURL(new RegExp(`/p/${doc.path}$`));
  await tab.reload();
  const stored = await call(context, "GET", `/api/pages/${doc.id}`);
  return { tab, article: tab.getByRole("main").locator(".wiki-prose"), stored: stored.content_md };
}

/** The cursor at the end of the document, in a new paragraph. */
async function newLineAtEnd(tab, editor) {
  await editor.click();
  await tab.keyboard.press("Control+End");
  // The editor learns of the moved selection from an asynchronous selectionchange event.
  await tab.evaluate(() => new Promise((resolve) => setTimeout(resolve, 0)));
  await tab.keyboard.press("Enter");
}

test("bold and italic overlapping", async () => {
  const { article, stored } = await typeAndSave("Betonung", "Anfang.", async (tab, editor) => {
    await newLineAtEnd(tab, editor);
    await tab.keyboard.type("eins ");
    await tab.keyboard.press("Control+b");
    await tab.keyboard.type("zwei ");
    await tab.keyboard.press("Control+i");
    await tab.keyboard.type("drei");
    await tab.keyboard.press("Control+b");
    await tab.keyboard.type(" vier");
    await tab.keyboard.press("Control+i");
    await tab.keyboard.type(" fünf");
  });
  await expect(article.locator("strong")).toHaveText("zwei drei");
  await expect(article.locator("strong em")).toHaveText("drei");
  await expect(article.locator("p").nth(1)).toHaveText("eins zwei drei vier fünf");
  await expect(article.locator("em").last()).toHaveText(/vier/);
  expect(stored).toBe("Anfang.\n\neins **zwei _drei_** _vier_ fünf");
});

test("a list of code blocks", async () => {
  // A list item starts with a line of text in the editor (as in Markdown, where a list
  // of code blocks has an empty first line): such a list comes from Markdown, and the
  // commands in it are typed in the browser.
  const markdown = "1. ```bash\n   npm ci\n   ```\n2. ```bash\n   npm test\n   ```";
  const { article, stored } = await typeAndSave("Befehle", markdown, async (tab, editor) => {
    for (const [command, more] of [
      ["npm ci", " --no-audit"],
      ["npm test", " -- --run"],
    ]) {
      await editor.getByText(command, { exact: true }).click();
      await tab.keyboard.press("End");
      await tab.keyboard.type(more);
    }
  });
  const items = article.locator("ol > li");
  await expect(items).toHaveCount(2);
  await expect(items.nth(0).locator("pre code")).toHaveText("npm ci --no-audit");
  await expect(items.nth(1).locator("pre code")).toHaveText("npm test -- --run");
  expect(stored).toBe(
    "1. ```bash\n   npm ci --no-audit\n   ```\n2. ```bash\n   npm test -- --run\n   ```",
  );
});

test("an image inside a sentence", async () => {
  let shown;
  const { article, stored } = await typeAndSave("Bild", "Anleitung", async (tab, editor) => {
    await newLineAtEnd(tab, editor);
    // Typing `![alt](src)` makes an image (the editor's input rule).
    await tab.keyboard.type("Klicke auf ![Speichern](/icons/save.png)");
    await expect(editor.getByRole("img", { name: "Speichern" })).toBeVisible();
    await tab.keyboard.type(" und dann auf Fertig.");
    shown = await editor.locator("p").nth(1).textContent();
  });
  expect(shown).toBe("Klicke auf  und dann auf Fertig."); // no `)` left behind
  const sentence = article.locator("p").nth(1);
  await expect(sentence).toHaveText(shown);
  await expect(sentence.getByRole("img", { name: "Speichern" })).toHaveAttribute(
    "src",
    "/icons/save.png",
  );
  expect(stored).toBe("Anleitung\n\nKlicke auf ![Speichern](/icons/save.png) und dann auf Fertig.");
});

test("Enter in a table cell keeps the table", async () => {
  const table = "| A | B |\n| --- | --- |\n| x | y |";
  const { article, stored } = await typeAndSave("Tabelle", table, async (tab, editor) => {
    await editor.getByText("x", { exact: true }).click();
    await tab.keyboard.press("End");
    // A cell holds one line of Markdown: Enter adds nothing, the text goes on.
    await tab.keyboard.press("Enter");
    await tab.keyboard.type("z");
  });
  await expect(article.locator("table tbody td").first()).toHaveText("xz");
  await expect(article.locator("table tbody td").nth(1)).toHaveText("y");
  expect(stored).toBe("| A | B |\n| --- | --- |\n| xz | y |");
});

test("a state that cannot be saved as Markdown is shown, and saved once it can", async () => {
  // Code in a table cell with a backslash right before `|`: no Markdown says that.
  const table = "| Befehl |\n| --- |\n| `a\\|b` |";
  const doc = await publishedPage(context, space.id, "Unsagbar", table);
  const tab = await context.newPage();
  await tab.goto(pageUrl(space, doc, "live"));
  const editor = tab.getByRole("textbox", { name: "Inhalt von „Unsagbar“" });
  // Wait for the editor first: while the page loads, its skeletons are status regions too.
  await expect(editor).toHaveAttribute("contenteditable", "true");
  await expect(tab.getByRole("status")).toHaveText("Synchronisiert");
  await editor.getByText("a|b").click();
  await tab.keyboard.press("Home");
  await tab.keyboard.press("ArrowRight");
  await tab.keyboard.type("\\");
  const notice = tab.getByText("lässt sich so nicht als Markdown speichern");
  await expect(notice).toBeVisible();
  await expect(editor).toHaveAttribute("contenteditable", "true");
  let stored = await call(context, "GET", `/api/pages/${doc.id}`);
  expect(stored.content_md).toBe(table);
  await tab.keyboard.press("Backspace");
  await tab.keyboard.type("x");
  await expect(notice).toBeHidden();
  await tab.getByRole("button", { name: "Fertig" }).click();
  await expect(tab).toHaveURL(new RegExp(`/p/${doc.path}$`));
  stored = await call(context, "GET", `/api/pages/${doc.id}`);
  expect(stored.content_md).toBe("| Befehl |\n| --- |\n| `ax\\|b` |");
});
