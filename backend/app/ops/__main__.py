"""`python -m app.ops ...` (see `app/ops/cli.py`)."""

import asyncio
import sys

from app.core.clock import SYSTEM_CLOCK
from app.core.config import get_settings
from app.ops.cli import run

if __name__ == "__main__":
    sys.exit(asyncio.run(run(sys.argv[1:], get_settings(), SYSTEM_CLOCK)))
