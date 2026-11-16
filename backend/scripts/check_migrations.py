"""Check that migrations after the last release only expand (plan M9 decision 22):

    uv run python -m scripts.check_migrations
    python3 -m scripts.check_migrations --require-released-head   # release.yml, at a tag

`alembic/RELEASED` names the revision of the last release (empty until the first tag).
At a release tag it must name the single head (`--require-released-head`): the tag is
the release, and the next one's revisions are checked against it.
In every revision after it, `upgrade()` may not drop a table, column, index or
constraint, change a column's type, rename a table or column, or `op.execute` SQL with
`DROP` or `RENAME`, unless the revision declares `contract_of = "<revision>"` and that
revision is the released one or older (expand in one release, contract in a later
one). Also: RELEASED names a known revision, and there is exactly one head.

Reads the files with `ast`, imports nothing. Prints each problem; exits 1 if any.
"""

import ast
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ALEMBIC = Path(__file__).resolve().parents[1] / "alembic"
CONTRACTING = {"drop_table", "drop_column", "drop_index", "drop_constraint", "rename_table"}
_SQL = re.compile(r"\b(DROP|RENAME)\b", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class Revision:
    path: Path
    revision: str
    down: tuple[str, ...]
    contract_of: str | None
    tree: ast.Module


def released_revision(path: Path) -> str:
    """The revision RELEASED names; empty before the first release."""
    return path.read_text().strip() if path.exists() else ""


def _value(tree: ast.Module, name: str) -> object:
    for node in tree.body:
        targets = (
            node.targets
            if isinstance(node, ast.Assign)
            else [node.target]
            if isinstance(node, ast.AnnAssign) and node.value is not None
            else []
        )
        if any(isinstance(t, ast.Name) and t.id == name for t in targets):
            assert isinstance(node, ast.Assign | ast.AnnAssign) and node.value is not None
            return ast.literal_eval(node.value)
    return None


def load(versions: Path) -> dict[str, Revision]:
    revisions: dict[str, Revision] = {}
    for path in sorted(versions.glob("*.py")):
        tree = ast.parse(path.read_text(), str(path))
        down = _value(tree, "down_revision")
        downs = _names(down)
        contract = _value(tree, "contract_of")
        rev = str(_value(tree, "revision"))
        revisions[rev] = Revision(path, rev, downs, str(contract) if contract else None, tree)
    return revisions


def _names(down: object) -> tuple[str, ...]:
    """`down_revision` as a tuple: none, one, or the parents of a merge."""
    if isinstance(down, str):
        return (down,)
    if isinstance(down, tuple | list):
        return tuple(str(d) for d in down)
    return ()


def _ancestors(revisions: dict[str, Revision], start: str) -> set[str]:
    """`start` and every revision before it."""
    seen, todo = set[str](), [start]
    while todo:
        rev = todo.pop()
        if rev in seen or rev not in revisions:
            continue
        seen.add(rev)
        todo.extend(revisions[rev].down)
    return seen


def _strings(node: ast.AST) -> list[str]:
    return [
        n.value for n in ast.walk(node) if isinstance(n, ast.Constant) and isinstance(n.value, str)
    ]


def contractions(tree: ast.Module) -> list[str]:
    """What `upgrade()` does that removes or renames schema."""
    found: list[str] = []
    for fn in tree.body:
        if not (isinstance(fn, ast.FunctionDef) and fn.name == "upgrade"):
            continue
        for node in ast.walk(fn):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
                continue
            name = node.func.attr
            changed = sorted({k.arg or "" for k in node.keywords} & {"type_", "new_column_name"})
            if name in CONTRACTING:
                found.append(name)
            elif name == "alter_column" and changed:
                found.append(f"alter_column({', '.join(changed)})")
            elif name == "execute" and any(_SQL.search(s) for s in _strings(node)):
                found.append("execute(DROP/RENAME)")
    return found


def check(versions: Path, released: str, *, require_released_head: bool = False) -> list[str]:
    revisions = load(versions)
    problems: list[str] = []
    downs = {d for r in revisions.values() for d in r.down}
    heads = sorted(set(revisions) - downs)
    if len(heads) != 1:
        problems.append(f"expected exactly one head, found {len(heads)}: {', '.join(heads)}")
    elif require_released_head and released != heads[0]:
        problems.append(f"RELEASED must name the head {heads[0]} at a release, not {released!r}")
    if not released:
        return problems
    if released not in revisions:
        return [*problems, f"RELEASED names an unknown revision: {released}"]
    shipped = _ancestors(revisions, released)
    for rev in sorted(set(revisions) - shipped):
        revision = revisions[rev]
        done = contractions(revision.tree)
        if not done:
            continue
        where = f"{revision.path.name} ({rev})"
        if revision.contract_of is None:
            problems.append(f"{where}: {', '.join(done)} after release {released}")
        elif revision.contract_of not in shipped:
            problems.append(
                f"{where}: contract_of {revision.contract_of} is not in release {released}"
            )
    return problems


def main(argv: list[str], *, alembic: Path = ALEMBIC) -> int:
    require = "--require-released-head" in argv
    released = released_revision(alembic / "RELEASED")
    problems = check(alembic / "versions", released, require_released_head=require)
    for problem in problems:
        print(problem)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
