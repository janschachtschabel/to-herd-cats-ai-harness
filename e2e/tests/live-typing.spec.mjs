// What people type in the live editor is what the page shows afterwards (review M2 S2,
// S3): each case is typed in Chromium, saved with "Fertig", and the page view checked
// after a reload. Every step waits for a state of the editor, never for a while (U8).
import { expect, test } from "@playwright/test";
import { call, publishedPage } from "./helpers.mjs";
import {
  caretIs,
  clickInto,
  newLineAtEnd,
  openLive,
  toEndOfBlock,
  typingCases,
} from "./live-typing-helpers.mjs";

const { shared, typeAndSave } = typingCases("Tippen");

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
      await clickInto(tab, editor, command);
      await toEndOfBlock(tab);
      await tab.keyboard.type(more);
      await caretIs(tab, { text: `${command}${more}` });
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

test("a list typed below a list shown as source is saved (review M2 U1)", async () => {
  // A list mixing task and plain items stays source (T14); a list typed below it was
  // read as part of it and could not be saved.
  const markdown = "# Plan\n\n- [ ] **Schritt 1**\n- Hinweis dazu";
  const { article, stored } = await typeAndSave("Plan", markdown, async (tab, editor) => {
    // The source block is the last one: ArrowDown at its end leaves it for a new line.
    await editor.click();
    await tab.keyboard.press("Control+End");
    await caretIs(tab, { atEnd: true, focused: true });
    await tab.keyboard.press("ArrowDown");
    await caretIs(tab, { atEnd: true, size: 0 });
    await tab.keyboard.type("- neuer Punkt");
    await expect(editor.locator("ul").last()).toHaveText("neuer Punkt");
  });
  expect(stored).toBe(`${markdown}\n\n* neuer Punkt`);
  await expect(article.locator("ul")).toHaveCount(2);
  await expect(article.locator("ul").last()).toHaveText("neuer Punkt");
});

test("undoing everything typed on a new page keeps the session (review M2 T6)", async () => {
  const doc = await publishedPage(shared.context, shared.space.id, "Neu", "");
  const tab = await shared.context.newPage();
  const { editor, status } = await openLive(tab, shared.space, doc, "Neu");
  await editor.click();
  await caretIs(tab, { focused: true });
  await tab.keyboard.type("# Titel");
  await tab.keyboard.press("Enter");
  await tab.keyboard.type("abc");
  for (let i = 0; i < 12; i++) await tab.keyboard.press("Control+z");
  await expect(editor).toHaveText("");
  // The browser's editor would stop at once on an empty shared document; the server's
  // answer comes with the sync of the undone state.
  await expect(status).toHaveText("Synchronisiert");
  await expect(editor).toHaveAttribute("contenteditable", "true");
  await tab.keyboard.type("weiter");
  await tab.getByRole("button", { name: "Fertig" }).click();
  await expect(tab).toHaveURL(new RegExp(`/p/${doc.path}$`));
  expect((await call(shared.context, "GET", `/api/pages/${doc.id}`)).content_md).toBe("weiter");
  await tab.close();
});

test("leaving right after a change saves it first and asks nothing (review M2 T5, U9)", async () => {
  const doc = await publishedPage(shared.context, shared.space.id, "Eilig", "Alter Text");
  const tab = await shared.context.newPage();
  const { editor } = await openLive(tab, shared.space, doc, "Eilig");
  await newLineAtEnd(tab, editor);
  await tab.keyboard.type("neuer Satz");
  const dialogs = [];
  tab.on("dialog", (dialog) => {
    dialogs.push(dialog.message());
    dialog.dismiss().catch(() => {});
  });
  // A link of the app (in-app navigation) right away: the save is still seconds off.
  await tab.getByRole("link", { name: shared.space.name }).first().click();
  await expect(tab).not.toHaveURL(/view=live/);
  expect(dialogs).toEqual([]);
  expect((await call(shared.context, "GET", `/api/pages/${doc.id}`)).content_md).toBe(
    "Alter Text\n\nneuer Satz",
  );
  await tab.close();
});

test("a state that cannot be saved as Markdown is shown, and saved once it can", async () => {
  // Code in a table cell with a backslash right before `|`: no Markdown says that.
  const table = "| Befehl |\n| --- |\n| `a\\|b` |";
  const doc = await publishedPage(shared.context, shared.space.id, "Unsagbar", table);
  const tab = await shared.context.newPage();
  const { editor } = await openLive(tab, shared.space, doc, "Unsagbar");
  await clickInto(tab, editor, "a|b");
  await tab.keyboard.press("Home");
  await caretIs(tab, { offset: 0 });
  await tab.keyboard.press("ArrowRight");
  await caretIs(tab, { offset: 1 });
  await tab.keyboard.type("\\");
  const notice = tab.getByText("lässt sich so nicht als Markdown speichern");
  await expect(notice).toBeVisible();
  await expect(editor).toHaveAttribute("contenteditable", "true");
  let stored = await call(shared.context, "GET", `/api/pages/${doc.id}`);
  expect(stored.content_md).toBe(table);
  // Leaving now asks, and says why (review M2 U9).
  const dialogs = [];
  tab.on("dialog", (dialog) => {
    dialogs.push(dialog.message());
    dialog.dismiss().catch(() => {});
  });
  await tab.getByRole("link", { name: shared.space.name }).first().click();
  await expect.poll(() => dialogs.length).toBe(1);
  expect(dialogs[0]).toMatch(/lässt sich nicht speichern/);
  expect(tab.url()).toContain("view=live");
  await editor.focus();
  await caretIs(tab, { offset: 2, focused: true });
  await tab.keyboard.press("Backspace");
  await tab.keyboard.type("x");
  await expect(notice).toBeHidden();
  await tab.getByRole("button", { name: "Fertig" }).click();
  await expect(tab).toHaveURL(new RegExp(`/p/${doc.path}$`));
  stored = await call(shared.context, "GET", `/api/pages/${doc.id}`);
  expect(stored.content_md).toBe("| Befehl |\n| --- |\n| `ax\\|b` |");
});
