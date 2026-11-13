"""Re-encrypt the stored AI secrets under the current key (docs/KI.md, "Schlüssel
wechseln"):

    HERD_SECRET_KEY=<new> HERD_SECRET_KEY_PREVIOUS=<old> \\
        uv run python -m scripts.rotate_secrets

All or nothing, in one transaction. Prints how many references were rotated; values
and keys are never printed. Afterwards HERD_SECRET_KEY_PREVIOUS can be removed.
"""

import asyncio
import sys

from app.core.config import get_settings
from app.core.db import Database
from app.modules.ai.secret_rotation import RotationFailed, rotate_secrets


async def main() -> int:
    if get_settings().secret_key is None:
        print("HERD_SECRET_KEY is not set", file=sys.stderr)
        return 1
    database = Database(get_settings().database())
    try:
        async with database.session_factory() as session:
            count = await rotate_secrets(session)
            await session.commit()
    except RotationFailed as failure:
        print(f"nothing changed: {failure}", file=sys.stderr)
        return 1
    finally:
        await database.dispose()
    print(f"rotated {count} secret reference(s)")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
