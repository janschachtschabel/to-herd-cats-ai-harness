"""Settings of operations (plan M9): backups. `Settings` inherits them, so
`get_settings()` stays the one source."""

from pathlib import Path

from pydantic_settings import BaseSettings


class OpsSettings(BaseSettings):
    # Where backup archives go (`python -m app.ops backup create`): a volume of its
    # own, mode 0700; the archives are not encrypted (docs: protect the volume).
    backup_dir: Path = Path("/backups")
