"""Review M9b, finding F6 (minor): a manifest whose values have the right types but
not the right form (a version that is no number, a time that is none) passes
`Manifest.from_json` and `verify_archive`, so the upload takes the archive; the check
and the replace then end in an unhandled ValueError (500) instead of a problem code."""

from pathlib import Path

import pytest

from app.core.config import get_settings
from tests.factories import login
from tests.factories_restore import make_archive, rewrite_manifest, source_settings
from tests.real_db import MakeRealClient, RealDb


@pytest.mark.parametrize(
    "changes", [{"pg_dump_version": "sixteen"}, {"created_at": "yesterday"}], ids=str
)
async def test_the_check_names_a_malformed_manifest_as_a_problem(
    real_db: RealDb,
    make_real_client: MakeRealClient,
    tmp_path: Path,
    data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    changes: dict[str, object],
) -> None:
    archive = await make_archive(source_settings(tmp_path, data_dir))
    monkeypatch.setattr(get_settings(), "backup_dir", archive.parent)
    rewrite_manifest(archive, **changes)
    owner = await make_real_client()
    await login(owner, real_db.owner_email)

    checked = await owner.post(f"/api/backups/archives/{archive.name}/check")

    assert checked.status_code == 200, checked.text
    assert checked.json()["can_replace"] is False
    assert checked.json()["problems"] == ["archive.format_unknown"]
