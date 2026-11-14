"""Which wiki page is an agent's memory in a space (plan M6 decision 10, `memory.py`).

One row per agent and space, made with the page by the agent's first `update_memory`
there. The page stays the agent's memory however it is renamed or moved within its
space (its id is what counts, not its path); a page in the trash, or no longer in
the row's space, is not, and the next `update_memory` makes a new one and points the
row at it.
"""

import uuid

from sqlalchemy import ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models_base import Base, OrgScoped


class AgentMemory(OrgScoped, Base):
    __tablename__ = "agent_memory"
    __table_args__ = (Index("ix_agent_memory_space_id", "space_id"),)

    agent_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("agent.id", ondelete="CASCADE"), primary_key=True
    )
    space_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("space.id", ondelete="CASCADE"), primary_key=True
    )
    page_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("page.id", ondelete="CASCADE"), unique=True
    )
