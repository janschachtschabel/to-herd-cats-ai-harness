// Live editing in real browsers (review M2 R18): two people in one page see each other
// and each other's text; "Fertig" shows the saved text at once (R3); a Markdown save
// ends the live session and both see the new text; a page the live editor would
// change is not opened and points to the Markdown editor (R1, 4422).
import { expect, test } from "@playwright/test";
import { MEMBER, OWNER, call, pageUrl, publishedPage, signIn, teamSpace } from "./helpers.mjs";

test.describe.configure({ mode: "serial" });

let anna;
let ben;

test.beforeEach(async ({ browser }) => {
  anna = await browser.newContext();
  ben = await browser.newContext();
  await signIn(anna, OWNER); // Ben signs in once `teamSpace` has made him
});

test.afterEach(async () => {
  await anna?.close();
  await ben?.close();
});

const surface = (page, title) => page.getByRole("textbox", { name: `Inhalt von „${title}“` });

async function typeAtEnd(page, title, text) {
  const editor = surface(page, title);
  await expect(editor).toHaveAttribute("contenteditable", "true");
  await editor.click();
  await page.keyboard.press("Control+End");
  await page.keyboard.press("Enter");
  await page.keyboard.type(text);
}

test("two people edit one page live; Fertig shows the saved text", async () => {
  const space = await teamSpace(anna, "Live");
  await signIn(ben, MEMBER);
  const doc = await publishedPage(anna, space.id, "Handbuch", "# Handbuch\n\nErster Absatz.");

  const a = await anna.newPage();
  await a.goto(pageUrl(space, doc));
  await a.getByRole("link", { name: "Gemeinsam bearbeiten" }).click();
  const b = await ben.newPage();
  await b.goto(pageUrl(space, doc, "live"));

  // Each sees the other.
  await expect(a.getByRole("list", { name: "Ebenfalls in der Seite" })).toContainText(MEMBER.name);
  await expect(b.getByRole("list", { name: "Ebenfalls in der Seite" })).toContainText("anna");

  await typeAtEnd(a, "Handbuch", "Satz von Anna.");
  await expect(surface(b, "Handbuch")).toContainText("Satz von Anna.");
  await typeAtEnd(b, "Handbuch", "Satz von Ben.");
  await expect(surface(a, "Handbuch")).toContainText("Satz von Ben.");

  // "Fertig": saved now, and the page shows it (not the text from before the session).
  await a.getByRole("button", { name: "Fertig" }).click();
  await expect(a).toHaveURL(new RegExp(`/p/${doc.path}$`));
  const article = a.getByRole("main");
  await expect(article).toContainText("Satz von Anna.");
  await expect(article).toContainText("Satz von Ben.");
  const stored = await call(anna, "GET", `/api/pages/${doc.id}`);
  expect(stored.content_md).toContain("Satz von Ben.");
});

test("a Markdown save ends the live session; the live editor shows the new text", async () => {
  const space = await teamSpace(anna, "Markdown");
  await signIn(ben, MEMBER);
  const doc = await publishedPage(anna, space.id, "Ablauf", "Alter Text.");

  const b = await ben.newPage();
  await b.goto(pageUrl(space, doc, "live"));
  await expect(surface(b, "Ablauf")).toHaveAttribute("contenteditable", "true");

  const a = await anna.newPage();
  await a.goto(pageUrl(space, doc, "edit"));
  await a.getByRole("textbox", { name: "Markdown" }).fill("Neuer Text aus dem Markdown-Editor.");
  await a.getByRole("button", { name: "Speichern" }).click();
  await expect(a.getByRole("main")).toContainText("Neuer Text aus dem Markdown-Editor.");

  await expect(b.getByText("außerhalb der Live-Sitzung geändert")).toBeVisible();
  await expect(surface(b, "Ablauf")).toContainText("Neuer Text aus dem Markdown-Editor.");
  await expect(surface(b, "Ablauf")).not.toContainText("Alter Text.");
});

test("a page the live editor would change is not opened (4422)", async () => {
  const space = await teamSpace(anna, "Treue");
  const doc = await publishedPage(anna, space.id, "Listen", "- eins\n\n* zwei");

  const a = await anna.newPage();
  await a.goto(pageUrl(space, doc, "live"));
  await expect(
    a.getByText("enthält Markdown, die der Live-Editor nicht unverändert"),
  ).toBeVisible();
  await expect(surface(a, "Listen")).not.toHaveAttribute("contenteditable", "true");
  await a.getByRole("link", { name: "Im Markdown-Editor bearbeiten" }).click();
  await expect(a.getByRole("textbox", { name: "Markdown" })).toHaveValue("- eins\n\n* zwei");
  const stored = await call(anna, "GET", `/api/pages/${doc.id}`);
  expect(stored.content_md).toBe("- eins\n\n* zwei");
});
