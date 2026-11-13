// Links typed in the live editor in Chromium (review M2 U5): only text starting with
// http://, https:// or www. becomes a link while typing, as the page view links it; a
// link can be taken off with the toolbar, by keyboard.
import { expect, test } from "@playwright/test";
import { caretIs, clickInto, newLineAtEnd, typingCases } from "./live-typing-helpers.mjs";

const { typeAndSave } = typingCases("Links");

test("file names and domain-like words stay text while typing", async () => {
  const { article, stored } = await typeAndSave("Dateien", "Anfang", async (tab, editor) => {
    await newLineAtEnd(tab, editor);
    await tab.keyboard.type("Siehe README.md und app.py sowie example.com und ");
    await tab.keyboard.type("https://example.org/a ");
    await expect(editor.getByRole("link")).toHaveCount(1);
  });
  expect(stored).toBe(
    "Anfang\n\nSiehe README.md und app.py sowie example.com und <https://example.org/a>",
  );
  await expect(article.getByRole("link")).toHaveCount(1);
  await expect(article.getByRole("link")).toHaveText("https://example.org/a");
});

test("a link is taken off with the toolbar, reached by keyboard", async () => {
  const markdown = "Siehe [Handbuch](https://example.org/handbuch) hier";
  const { article, stored } = await typeAndSave("Entlinken", markdown, async (tab, editor) => {
    const unlink = tab.getByRole("button", { name: "Link entfernen" });
    await expect(unlink).toBeDisabled();
    await clickInto(tab, editor, "Handbuch", "Siehe Handbuch hier");
    await expect(unlink).toBeEnabled();
    // From the editor back to the toolbar's last button with Shift+Tab, then Enter.
    await tab.keyboard.press("Shift+Tab");
    await expect(unlink).toBeFocused();
    await tab.keyboard.press("Enter");
    await expect(editor.getByRole("link")).toHaveCount(0);
    await caretIs(tab, { text: "Siehe Handbuch hier" });
  });
  expect(stored).toBe("Siehe Handbuch hier");
  await expect(article.getByRole("link")).toHaveCount(0);
});
