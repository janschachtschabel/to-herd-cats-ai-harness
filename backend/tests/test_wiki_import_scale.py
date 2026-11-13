"""An import of thousands of pages stays one transaction of a bounded number of
statements per page (review M2 R19: 1,999 pages took 61-80 s): the rights are read
once, slugs and order once per folder, and a page is published as it is created."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import event
from sqlalchemy.engine import Engine

from tests.factories_wiki import Wiki
from tests.test_wiki_import_export import _import, _tree, _zip


@contextmanager
def _statements() -> Iterator[list[str]]:
    seen: list[str] = []

    def count(_conn: Any, _cursor: Any, statement: str, *_args: Any) -> None:
        seen.append(statement)

    event.listen(Engine, "before_cursor_execute", count)
    try:
        yield seen
    finally:
        event.remove(Engine, "before_cursor_execute", count)


def _folder(name: str, count: int) -> dict[str, bytes | str]:
    files: dict[str, bytes | str] = {f"{name}.md": "---\ntags: [a, b]\n---\nOrdner\n"}
    for i in range(count):
        files[f"{name}/seite-{i:03}.md"] = f"---\ntitle: Seite {i}\ntags: [a]\n---\nText {i}\n"
    return files


async def _cost(wiki: Wiki, name: str, count: int) -> int:
    with _statements() as seen:
        r = await _import(wiki.admin, wiki.space_id, _zip(_folder(name, count)))
    assert r.status_code == 200, r.text
    assert r.json()["created"] == count + 1
    return len(seen)


async def test_each_page_costs_a_bounded_number_of_statements(wiki: Wiki) -> None:
    small, large = await _cost(wiki, "klein", 10), await _cost(wiki, "gross", 40)
    per_page = (large - small) / 30
    print(f"statements: {small} for 11 pages, {large} for 41, {per_page:.1f} per page")
    assert per_page <= 8, (small, large)  # 28.6 before review M2 R19
    pages = await _tree(wiki.admin, wiki.space_id)
    assert pages["gross/seite-039"]["status"] == "published"
    assert [pages[f"gross/seite-{i:03}"]["sort_order"] for i in range(3)] == [0, 1, 2]
