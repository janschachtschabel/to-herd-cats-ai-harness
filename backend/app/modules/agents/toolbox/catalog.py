"""Every tool a run can have (plan M6 decision 3). A tool that is not listed here
can never run: the loop offers only listed tools, and a call to any other name is a
bad call.

To add a tool: write its arguments' model and its `run` (see `base.py`; reading tools
in `reading.py`), and list it here with its description.
"""

from app.modules.agents.toolbox import reading
from app.modules.agents.toolbox.base import ToolSpec

CATALOG: dict[str, ToolSpec] = {
    spec.name: spec
    for spec in (
        ToolSpec(
            "search",
            "Full-text search in the wiki pages and tickets you may read. Returns the best "
            "hits with type, id or key, title, space and a short snippet.",
            reading.SearchArgs,
            reading.search,
        ),
        ToolSpec(
            "read_page",
            "Read one wiki page by its id (from a search hit). Returns its Markdown.",
            reading.ReadPageArgs,
            reading.read_page,
        ),
        ToolSpec(
            "read_ticket",
            "Read one ticket by its key (such as HC-12). Returns its fields and text.",
            reading.ReadTicketArgs,
            reading.read_ticket,
        ),
    )
}


def offered() -> list[ToolSpec]:
    """The tools a run offers the model, in the catalog's order."""
    return list(CATALOG.values())
