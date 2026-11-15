"""Rows that bound a run from outside its own steps (split from `models.py`).

`run_cancel_request`: someone asked a run to stop (spec 8.3); checked before every
step and in the transaction that ends the run (`cancelled`).

`ai_rate_window`: a connection's `requests_per_minute`, counted across workers.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models_base import Base, OrgScoped


class RunCancelRequest(OrgScoped, Base):
    """Someone asked the run to stop: once per run, before it is done."""

    __tablename__ = "run_cancel_request"

    run_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("run.id", ondelete="CASCADE"), primary_key=True
    )
    requested_by: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("app_user.id"), nullable=False
    )


class RateWindow(OrgScoped, Base):
    """`requests_per_minute` of a connection, across workers: the calls started in the
    current window (spec 12.4: no such state in memory)."""

    __tablename__ = "ai_rate_window"

    connection_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("ai_connection.id", ondelete="CASCADE"), primary_key=True
    )
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    calls: Mapped[int] = mapped_column(Integer, nullable=False)
