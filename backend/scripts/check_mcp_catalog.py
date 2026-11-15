"""Check catalogue entries (docs/MCP.md, "Katalog"): the shipped ones, or the files in
the directories given (an operator's `HERD_MCP_CATALOG_DIR` before it goes live):

    uv run python -m scripts.check_mcp_catalog [DIR ...]

Prints each entry's id and each problem (file and reason, never the content); exits 1
if any file has a problem. CI runs it on `app/mcp/catalog/`.
"""

import sys
from pathlib import Path

from app.modules.mcp_catalog.loader import SHIPPED_DIR, Problem, Source, load_directory


def main(argv: list[str]) -> int:
    directories = [Path(arg) for arg in argv] or [SHIPPED_DIR]
    shipped = {entry.id for _, entry in load_directory(SHIPPED_DIR, Source.SHIPPED)[0]}
    failed = False
    for directory in directories:
        entries, problems = load_directory(directory, Source.OPERATOR)
        for file, entry in entries:
            if directory != SHIPPED_DIR and entry.id in shipped:
                problems.append(Problem(Source.OPERATOR, file, f"id {entry.id} already taken"))
            else:
                print(f"ok {directory / file}: {entry.id} ({len(entry.tools)} tools)")
        for problem in problems:
            print(f"problem {directory / problem.file}: {problem.reason}", file=sys.stderr)
        failed = failed or bool(problems) or not entries
        if not entries and not problems:
            print(f"problem {directory}: no entries", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
