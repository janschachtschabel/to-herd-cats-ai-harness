"""The demo's two wiki pages (M2), through the public API: "Handbuch" and below it
"Urlaub", both published; "Urlaub" is changed and restored, so its discussion gets
three system entries (created, published, version restored)."""

import httpx

from scripts.demo_api import call

HANDBOOK = """# Handbuch

Wie wir im Team Nord arbeiten. Fragen gern in **#team-nord** oder in der Diskussion
einer Seite.

- [[Urlaub]]
"""

LEAVE = """# Urlaub

- 30 Tage im Jahr, Teilzeit anteilig.
- Anträge zwei Wochen vorher im Team abstimmen.
"""


async def build(anna: httpx.AsyncClient, space_id: str) -> tuple[str, str]:
    """Anna writes both pages; returns the ids of "Handbuch" and "Urlaub"."""
    pages = f"/api/spaces/{space_id}/pages"
    handbook = await call(anna, "POST", pages, {"title": "Handbuch", "content_md": HANDBOOK})
    publish = {"version": handbook["version"]}
    await call(anna, "POST", f"/api/pages/{handbook['id']}/publish", publish)
    leave = await call(
        anna,
        "POST",
        pages,
        {"title": "Urlaub", "content_md": LEAVE, "parent_id": handbook["id"]},
    )
    page_id = str(leave["id"])
    publish = {"version": leave["version"]}
    leave = await call(anna, "POST", f"/api/pages/{page_id}/publish", publish)
    edit = {"content_md": LEAVE + "\nEntwurf: 35 Tage für alle.\n", "version": leave["version"]}
    leave = await call(anna, "PATCH", f"/api/pages/{page_id}", edit)
    restore = {"version": leave["version"]}
    await call(anna, "POST", f"/api/pages/{page_id}/versions/1/restore", restore)
    return str(handbook["id"]), page_id
