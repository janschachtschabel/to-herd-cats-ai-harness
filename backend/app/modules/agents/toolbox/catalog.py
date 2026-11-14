"""Every tool a run can have (plan M6 decision 3), with the lowest autonomy level
whose default allows it (1 reads, 2 proposes, 3 writes inside; spec 8.2) and its
effect. A tool that is not listed here can never run: a run offers only listed tools
its grants allow (`policy.py`), and a call to any other name is a bad call.

To add a tool: write its arguments' model and its `run` (see `base.py`; reading tools
in `reading.py`), and list it here with its description, level and effect. A writing
tool writes through the services with `ctx.actor` in `ctx.session` (its effect and
its journal entry commit together); it checks its rights itself, before it writes.
"""

from app.modules.agents.toolbox import reading
from app.modules.agents.toolbox.base import Effect, ToolSpec

READ = Effect.READ

CATALOG: dict[str, ToolSpec] = {
    spec.name: spec
    for spec in (
        ToolSpec(
            "search",
            "Full-text search in the wiki pages and tickets you may read. Returns the best "
            "hits with type, id or key, title, space and a short snippet.",
            reading.SearchArgs,
            reading.search,
            1,
            READ,
        ),
        ToolSpec(
            "read_page",
            "Read one wiki page by its id (from a search hit). Returns its Markdown.",
            reading.ReadPageArgs,
            reading.read_page,
            1,
            READ,
        ),
        ToolSpec(
            "read_ticket",
            "Read one ticket by its key (such as HC-12). Returns its fields and text.",
            reading.ReadTicketArgs,
            reading.read_ticket,
            1,
            READ,
        ),
    )
}


def offered() -> list[ToolSpec]:
    """The tools a run offers the model, in the catalog's order."""
    return list(CATALOG.values())
