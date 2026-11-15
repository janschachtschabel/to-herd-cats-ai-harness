"""Released migrations only expand (plan M9 decision 22): `scripts/check_migrations.py`
refuses, in every revision after the one `alembic/RELEASED` names, what removes or
renames schema, unless the revision declares `contract_of` a revision the release
already had. Before the first release (RELEASED empty) nothing is refused."""

from pathlib import Path

import pytest

from scripts.check_migrations import check, released_revision

HEADER = '''"""{doc}"""
import sqlalchemy as sa
from alembic import op

revision = "{rev}"
down_revision = {down}
{extra}

def upgrade() -> None:
{body}


def downgrade() -> None:
    op.drop_table("anything")
'''


def _write(versions: Path, rev: str, down: str | None, body: str, extra: str = "") -> None:
    text = HEADER.format(
        doc=rev,
        rev=rev,
        down=repr(down),
        extra=extra,
        body="\n".join("    " + line for line in body.strip().splitlines()),
    )
    (versions / f"{rev}.py").write_text(text)


@pytest.fixture
def versions(tmp_path: Path) -> Path:
    v = tmp_path / "versions"
    v.mkdir()
    _write(v, "a1", None, 'op.create_table("t", sa.Column("id", sa.Integer()))')
    _write(v, "b2", "a1", 'op.add_column("t", sa.Column("x", sa.Integer()))')
    return v


def test_before_the_first_release_everything_passes(versions: Path) -> None:
    _write(versions, "c3", "b2", 'op.drop_column("t", "x")')
    assert check(versions, "") == []


def test_expanding_after_a_release_passes(versions: Path) -> None:
    _write(
        versions,
        "c3",
        "b2",
        """
op.add_column("t", sa.Column("y", sa.Integer()))
op.create_index("ix_t_y", "t", ["y"])
op.alter_column("t", "y", nullable=True)
op.execute("UPDATE t SET y = 1")
""",
    )
    assert check(versions, "b2") == []


@pytest.mark.parametrize(
    "body",
    [
        'op.drop_table("t")',
        'op.drop_column("t", "x")',
        'op.drop_index("ix_t_x", table_name="t")',
        'op.drop_constraint("fk_t", "t")',
        'op.alter_column("t", "x", type_=sa.BigInteger())',
        'op.alter_column("t", "x", new_column_name="z")',
        'op.rename_table("t", "u")',
        'op.execute("ALTER TABLE t DROP COLUMN x")',
        'op.execute(sa.text("alter table t rename column x to z"))',
    ],
)
def test_contracting_after_a_release_is_refused(versions: Path, body: str) -> None:
    _write(versions, "c3", "b2", body)
    problems = check(versions, "b2")
    assert len(problems) == 1 and "c3" in problems[0]


def test_a_revision_of_the_release_itself_is_not_checked(versions: Path) -> None:
    _write(versions, "c3", "b2", 'op.drop_column("t", "x")')
    assert check(versions, "c3") == []


def test_contract_of_a_released_revision_passes(versions: Path) -> None:
    _write(versions, "c3", "b2", 'op.drop_column("t", "x")', extra='contract_of = "b2"')
    assert check(versions, "b2") == []
    _write(versions, "d4", "c3", 'op.drop_column("t", "y")', extra='contract_of = "a1"')
    assert check(versions, "c3") == []


def test_contract_of_an_unreleased_revision_is_refused(versions: Path) -> None:
    _write(versions, "c3", "b2", 'op.add_column("t", sa.Column("y", sa.Integer()))')
    _write(versions, "d4", "c3", 'op.drop_column("t", "y")', extra='contract_of = "c3"')
    problems = check(versions, "b2")
    assert len(problems) == 1 and "d4" in problems[0] and "contract_of" in problems[0]


def test_an_unknown_release_and_two_heads_are_refused(versions: Path) -> None:
    assert any("RELEASED" in p for p in check(versions, "zz"))
    _write(versions, "c3", "a1", 'op.add_column("t", sa.Column("y", sa.Integer()))')
    assert any("head" in p for p in check(versions, ""))


def test_the_repository_passes_and_names_no_release_yet() -> None:
    root = Path(__file__).resolve().parents[1] / "alembic"
    assert released_revision(root / "RELEASED") == ""
    assert check(root / "versions", released_revision(root / "RELEASED")) == []
