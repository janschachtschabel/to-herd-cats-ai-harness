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
  // The editor's own status (while the page loads, its skeletons are status regions too).
  await expect(tab.getByRole("region", { name: title }).getByRole("status")).toHaveText(
    "Synchronisiert",
  );
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

test("undoing everything typed on a new page keeps the session (review M2 T6)", async () => {
  const doc = await publishedPage(context, space.id, "Neu", "");
  const tab = await context.newPage();
  await tab.goto(pageUrl(space, doc, "live"));
  const editor = tab.getByRole("textbox", { name: "Inhalt von „Neu“" });
  await expect(editor).toHaveAttribute("contenteditable", "true");
  const status = tab.getByRole("region", { name: "Neu" }).getByRole("status");
  await expect(status).toHaveText("Synchronisiert");
  await editor.click();
  await tab.keyboard.type("# Titel");
  await tab.keyboard.press("Enter");
  await tab.keyboard.type("abc");
  for (let i = 0; i < 12; i++) await tab.keyboard.press("Control+z");
  await expect(editor).toHaveText("");
  await tab.waitForTimeout(500);
  await expect(status).toHaveText("Synchronisiert");
  await expect(editor).toHaveAttribute("contenteditable", "true");
  await tab.keyboard.type("weiter");
  await tab.getByRole("button", { name: "Fertig" }).click();
  await expect(tab).toHaveURL(new RegExp(`/p/${doc.path}$`));
  expect((await call(context, "GET", `/api/pages/${doc.id}`)).content_md).toBe("weiter");
  await tab.close();
});

test("leaving right after a change asks first (review M2 T5)", async () => {
  const doc = await publishedPage(context, space.id, "Eilig", "Alter Text");
  const tab = await context.newPage();
  await tab.goto(pageUrl(space, doc, "live"));
  const editor = tab.getByRole("textbox", { name: "Inhalt von „Eilig“" });
  await expect(editor).toHaveAttribute("contenteditable", "true");
  await expect(tab.getByRole("region", { name: "Eilig" }).getByRole("status")).toHaveText(
    "Synchronisiert",
  );
  await newLineAtEnd(tab, editor);
  await tab.keyboard.type("neuer Satz");
  const dialogs = [];
  tab.on("dialog", (dialog) => {
    dialogs.push(dialog.type());
    dialog.dismiss().catch(() => {});
  });
  // A link of the app (in-app navigation) right away: the save is still seconds off.
  await tab.getByRole("link", { name: space.name }).first().click();
  await expect.poll(() => dialogs.length).toBeGreaterThan(0);
  expect(tab.url()).toContain("view=live");
  // Once stored and acknowledged, leaving asks nothing.
  await expect
    .poll(async () => (await call(context, "GET", `/api/pages/${doc.id}`)).content_md)
    .toContain("neuer Satz");
  await tab.waitForTimeout(300);
  const asked = dialogs.length;
  await tab.getByRole("link", { name: space.name }).first().click();
  await expect(tab).not.toHaveURL(/view=live/);
  expect(dialogs.length).toBe(asked);
  await tab.close();
});

test("a state that cannot be saved as Markdown is shown, and saved once it can", async () => {
  // Code in a table cell with a backslash right before `|`: no Markdown says that.
  const table = "| Befehl |\n| --- |\n| `a\\|b` |";
  const doc = await publishedPage(context, space.id, "Unsagbar", table);
  const tab = await context.newPage();
  await tab.goto(pageUrl(space, doc, "live"));
  const editor = tab.getByRole("textbox", { name: "Inhalt von „Unsagbar“" });
  await expect(editor).toHaveAttribute("contenteditable", "true");
  // The editor's own status (while the page loads, its skeletons are status regions too).
  await expect(tab.getByRole("region", { name: "Unsagbar" }).getByRole("status")).toHaveText(
    "Synchronisiert",
  );
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
