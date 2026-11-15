"""API shapes of a token's usage (plan M8 decision 6)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.modules.mcp_tools.models import Outcome


class McpCallOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tool: str
    outcome: Outcome
    duration_ms: int
    created_at: datetime
