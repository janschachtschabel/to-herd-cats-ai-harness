"""Access tokens and the MCP settings as the API takes and shows them. A token's clear
text is only in `TokenCreatedOut`, the answer to creating it; nothing shows its hash."""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.modules.ai.models import DataLocation
from app.modules.tokens.models import (
    MAX_DAYS,
    MAX_NAME_CHARS,
    MAX_SCOPE_SPACES,
    AccessToken,
    TokenKind,
    TokenMode,
)
from app.modules.tokens.repository import Listed

Name = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=MAX_NAME_CHARS,
        pattern=r"^[^\x00-\x1f\x7f]+$",
    ),
]


class TokenIn(BaseModel):
    """`space_ids`: the spaces the token may reach (each one the person reads, else
    422 `token.space_invalid`); left out or null: all the person's spaces.
    `expires_in_days`: required, 1 to 365."""

    model_config = ConfigDict(extra="forbid")

    name: Name
    mode: TokenMode
    expires_in_days: int = Field(ge=1, le=MAX_DAYS)
    space_ids: list[uuid.UUID] | None = Field(
        default=None, min_length=1, max_length=MAX_SCOPE_SPACES
    )


class TokenOut(BaseModel):
    """`agent_id`: an agent token's external agent (kind `agent`), else null."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: TokenKind
    agent_id: uuid.UUID | None = None
    name: str
    mode: TokenMode
    space_ids: list[uuid.UUID] | None
    expires_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime


class TokenCreatedOut(TokenOut):
    """`secret`: the token's clear text, shown this once and stored nowhere."""

    secret: str

    @classmethod
    def of(cls, token: AccessToken, secret: str) -> "TokenCreatedOut":
        return cls(**TokenOut.model_validate(token).model_dump(), secret=secret)


class TokenUserOut(BaseModel):
    id: uuid.UUID
    name: str


class TokenAgentOut(BaseModel):
    id: uuid.UUID
    name: str


class AdminTokenOut(TokenOut):
    """A token in the admins' list: its metadata and whose it is (`user`: its person;
    for an agent token the agent's responsible person, and `agent` the agent)."""

    user: TokenUserOut
    agent: TokenAgentOut | None = None

    @classmethod
    def of(cls, listed: Listed) -> "AdminTokenOut":
        shown = TokenOut.model_validate(listed.token).model_dump()
        token = listed.token
        agent = None
        if token.agent_id is not None and listed.agent_name is not None:
            agent = TokenAgentOut(id=token.agent_id, name=listed.agent_name)
        user = TokenUserOut(id=token.user_id, name=listed.user_name)
        return cls(**shown, user=user, agent=agent)


class McpSettingsOut(BaseModel):
    """`enabled`: whether every active person but guests holds `mcp.use`.
    `data_location`: what an MCP client counts as for the spaces' AI policy."""

    enabled: bool
    data_location: DataLocation
    version: int


class McpSettingsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool
    data_location: DataLocation
    version: int
