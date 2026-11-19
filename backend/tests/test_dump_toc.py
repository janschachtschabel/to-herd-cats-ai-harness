"""What of an archive's dump a restore runs (review M9b F1, `ops/dump_toc.py`): our
schema's entries only, grants left out, anything else refuses the archive; pg_restore
and psql must know `\\restrict`."""

import asyncio
import io
import tarfile
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from sqlalchemy import text

from app.ops.dump_toc import FOREIGN, FUNCTIONS, TRIGGERS, judge, list_dump
from app.ops.manifest import Member
from app.ops.pgtools import ToolFailed, child_env, restrict_capable
from app.ops.restore_checks import _dump_problems, _misnamed
from tests.factories_restore import Target
from tests.real_db import RealDb
from tests.replace_helpers import sql

OURS = """;
; Archive created at 2026-11-18 22:46:37 UTC
;
290; 1255 12677119 FUNCTION public herd_conversation_kind_fixed() herd
271; 1259 12678238 TABLE public access_token herd
4100; 0 12678238 TABLE DATA public access_token herd
3600; 2606 12678500 CONSTRAINT public access_token pk_access_token herd
3700; 1259 12678600 INDEX public ix_access_token_user herd
4200; 2606 12678700 FK CONSTRAINT public access_token fk_access_token_user herd
280; 1259 12678800 SEQUENCE public counter_seq herd
4300; 0 0 SEQUENCE OWNED BY public counter_seq herd
4301; 0 0 SEQUENCE SET public counter_seq herd
3400; 2604 12678900 DEFAULT public counter id herd
4329; 2620 12677120 TRIGGER public conversation conversation_kind_fixed herd
4400; 0 0 ACL - SCHEMA public pg_database_owner
4401; 826 12679000 DEFAULT ACL - DEFAULT PRIVILEGES FOR TABLES herd
4402; 0 0 COMMENT - SCHEMA public herd
"""


def test_our_entries_are_restored_and_grants_left_out() -> None:
    use_list = judge(OURS)
    kept = [line.split(";")[0] for line in use_list.splitlines()]
    assert kept == ["290", "271", "4100", "3600", "3700", "4200", "280", "4300", "4301"] + [
        "3400",
        "4329",
    ]


@pytest.mark.parametrize(
    "entry",
    [
        # Schema public after a replace, or with an owner set by hand (review M9b F2-2).
        "5; 2615 15297822 SCHEMA - public herd",
        "5; 2615 2200 SCHEMA - public pg_database_owner",
        "4403; 0 0 COMMENT - SCHEMA public pg_database_owner",
        # plpgsql dropped and created again: the one extension taken.
        "1; 3079 15297826 EXTENSION - plpgsql ",
        "4404; 0 0 COMMENT - EXTENSION plpgsql ",
    ],
)
def test_schema_public_and_plpgsql_are_taken_and_left_out(entry: str) -> None:
    """The swap makes schema `public` itself and every installation has plpgsql: the
    entries are no reason to refuse and nothing the restore runs."""
    assert judge(OURS + entry + "\n") == judge(OURS)


@pytest.mark.parametrize(
    "entry",
    [
        "4500; 0 0 COMMENT public TABLE note herd",
        "4510; 2615 16508 SCHEMA - public2 herd",
        "4511; 2615 16509 SCHEMA - public owner with spaces",
        "4512; 3079 16510 EXTENSION - pg_trgm ",
        "4513; 0 0 COMMENT - EXTENSION pg_trgm ",
        "4514; 3079 16511 EXTENSION - plpgsql2 ",
        "4501; 3079 16400 EXTENSION - dblink",
        "4502; 1255 16500 FUNCTION public run_anything() herd",
        "4503; 1255 16501 FUNCTION public herd_work_item_hierarchy(text) herd",
        "4504; 2620 16502 TRIGGER public message message_backdoor herd",
        "4505; 1259 16503 VIEW public everything herd",
        "4506; 1259 16504 TABLE other secrets herd",
        "4507; 2615 16505 SCHEMA - other herd",
        "4508; 3466 16506 EVENT TRIGGER - on_ddl herd",
        "4509; 2618 16507 RULE public page on_select herd",
        "not a toc line",
    ],
)
def test_anything_else_refuses_the_dump(entry: str) -> None:
    with pytest.raises(ToolFailed) as refused:
        judge(OURS + entry + "\n")
    assert refused.value.code == FOREIGN


async def test_the_allowed_names_are_the_migrated_schemas(real_db: RealDb) -> None:
    """A migration that adds a function or a trigger adds it to the list too."""
    async with real_db.database.session_factory() as session:
        functions = set(
            (
                await session.scalars(
                    text("SELECT proname FROM pg_proc WHERE pronamespace = 'public'::regnamespace")
                )
            ).all()
        )
        triggers = set(
            await session.scalars(text("SELECT tgname FROM pg_trigger WHERE NOT tgisinternal"))
        )
    assert functions == FUNCTIONS
    assert triggers == TRIGGERS


@pytest.mark.parametrize(
    ("version", "capable"),
    [
        ("15.14", False),
        ("16", False),
        ("16.9", False),
        ("16.10", True),
        ("16.15", True),
        ("17.5", False),
        ("17.6", True),
        ("18", True),
        ("19.1", True),
    ],
)
def test_restrict_needs_a_fixed_release(version: str, capable: bool) -> None:
    assert restrict_capable(version) is capable


def test_a_file_key_ends_in_its_own_checksum() -> None:
    sha = "ab" * 32
    member = Member(sha256=sha, size=3)
    assert not _misnamed(f"files/attachments/org/{sha}", member)
    assert _misnamed(f"files/attachments/org/{'cd' * 32}", member)
    assert not _misnamed("db.dump", member)


async def _chunks(data: bytes) -> AsyncIterator[bytes]:
    for start in range(0, len(data), 4096):
        yield data[start : start + 4096]


async def _dump(target: Target, tmp_path: Path) -> bytes:
    out = tmp_path / "source.dump"
    process = await asyncio.create_subprocess_exec(
        "pg_dump", "--format=custom", "--no-password", f"--file={out}",
        env=child_env(target.settings),
    )  # fmt: skip
    assert await process.wait() == 0
    return out.read_bytes()


async def test_the_check_lists_the_dump_and_names_a_foreign_one(
    target: Target, tmp_path: Path
) -> None:
    await sql(target.settings, "CREATE TABLE note (a int)")
    ours = await _dump(target, tmp_path)
    listing = await list_dump(_chunks(ours))
    assert listing.use_list.count("\n") == 2  # the table and its data
    assert b"".join([chunk async for chunk in listing.dump]) == ours  # whole again

    await sql(target.settings, "COMMENT ON TABLE note IS 'whatever'")
    foreign = await _dump(target, tmp_path)
    archive = tmp_path / "foreign.tar"
    with tarfile.open(archive, "w", format=tarfile.PAX_FORMAT) as tar:
        info = tarfile.TarInfo("herd/db.dump")
        info.size = len(foreign)
        tar.addfile(info, io.BytesIO(foreign))
    assert await _dump_problems(archive) == [FOREIGN]
