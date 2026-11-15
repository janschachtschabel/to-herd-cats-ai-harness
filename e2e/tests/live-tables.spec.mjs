// Tables in the live editor, typed and pasted in Chromium, saved with "Fertig", and the
// page view checked after a reload: a table stays one table (review M2 T3, T8, U4).
import { expect, test } from "@playwright/test";
import { clickInto, toEndOfBlock, typingCases } from "./live-typing-helpers.mjs";

const { shared, typeAndSave } = typingCases("Tabellen");

test("Enter and Shift+Enter in a table cell keep the table (review M2 T8)", async () => {
  const table = "| A | B |\n| --- | --- |\n| x | y |";
  const { article, stored } = await typeAndSave("Tabelle", table, async (tab, editor) => {
    for (const [cell, keys] of [
      ["x", ["Enter", "Shift+Enter"]],
      ["A", ["Shift+Enter", "Enter"]],
    ]) {
      await clickInto(tab, editor, cell);
      await toEndOfBlock(tab);
      // A cell holds one line of Markdown: these keys add nothing, the text goes on.
      for (const key of keys) await tab.keyboard.press(key);
      await tab.keyboard.type("z");
    }
  });
  await expect(article.locator("table")).toHaveCount(1);
  await expect(article.locator("table thead th").first()).toHaveText("Az");
  await expect(article.locator("table tbody td").first()).toHaveText("xz");
  await expect(article.locator("table tbody td").nth(1)).toHaveText("y");
  expect(stored).toBe("| Az | B |\n| --- | --- |\n| xz | y |");
});

test("a row added with Tab to a table with an aligned column is saved (review M2 T3)", async () => {
  const table = "| Name | Wert |\n| --- | --: |\n| a | 1 |";
  const { article, stored } = await typeAndSave("Inventar", table, async (tab, editor) => {
    await clickInto(tab, editor, "1");
    await toEndOfBlock(tab);
    await tab.keyboard.press("Tab"); // a new row
    await tab.keyboard.type("b");
    await tab.keyboard.press("Tab");
    await tab.keyboard.type("2");
    await expect(editor.locator("tr")).toHaveCount(3);
    await expect(tab.getByText("lässt sich so nicht als Markdown speichern")).toBeHidden();
  });
  await expect(article.locator("table tbody tr")).toHaveCount(2);
  await expect(article.locator("table tbody tr").nth(1).locator("td").nth(1)).toHaveText("2");
  expect(stored).toBe("| Name | Wert |\n| --- | --: |\n| a | 1 |\n| b | 2 |");
});

/** Puts `items` (type → text) on the clipboard and pastes with Ctrl+V. */
async function paste(tab, items) {
  await tab.evaluate(async (entries) => {
    const item = new ClipboardItem(
      Object.fromEntries(entries.map(([type, text]) => [type, new Blob([text], { type })])),
    );
    await navigator.clipboard.write([item]);
  }, Object.entries(items));
  await tab.keyboard.press("Control+V");
}

const NUMBERS = "| Name | Wert |\n| --- | --: |\n| a | 1 |\n| b | 2 |\n| c | 3 |";

for (const [name, items, cell] of [
  ["two lines of text", { "text/plain": "erste Zeile\nzweite Zeile" }, "berste Zeile zweite Zeile"],
  [
    "two HTML paragraphs",
    { "text/html": "<p>erste Zeile</p><p>zweite Zeile</p>", "text/plain": "x" },
    "berste Zeile zweite Zeile",
  ],
  [
    "rows of a spreadsheet",
    {
      "text/html": "<table><tr><td>p</td><td>q</td></tr><tr><td>r</td><td>s</td></tr></table>",
      "text/plain": "p\tq\nr\ts",
    },
    "bp q r s",
  ],
]) {
  test(`pasting ${name} into a cell keeps the table (review M2 U4)`, async () => {
    await shared.context.grantPermissions(["clipboard-read", "clipboard-write"]);
    const { article, stored } = await typeAndSave(
      `Einfügen ${name}`,
      NUMBERS,
      async (tab, editor) => {
        await clickInto(tab, editor, "b");
        await toEndOfBlock(tab);
        await paste(tab, items);
        await expect(editor.getByText(cell, { exact: true })).toBeVisible();
        await expect(editor.locator("table")).toHaveCount(1);
      },
    );
    await expect(article.locator("table")).toHaveCount(1);
    await expect(article.locator("table tbody tr")).toHaveCount(3);
    await expect(article.locator("table tbody tr").nth(1).locator("td").first()).toHaveText(cell);
    expect(stored).toBe(NUMBERS.replace("| b |", `| ${cell} |`));
  });
}
