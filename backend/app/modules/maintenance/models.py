"""Maintenance (plan M9 decision 9): one row per organisation saying whether the
installation is in maintenance, why (`restore`: an archive is replacing the running
installation) and since when. While a row is active, the API answers 503 and the
worker's loops pause (`cache.py`, `middleware.py`). `version` counts every change: a
change made against a state that moved on is refused (409)."""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models_base import Base, OrgScoped, UuidPk


class MaintenanceReason(StrEnum):
    RESTORE = "restore"


class Maintenance(UuidPk, OrgScoped, Base):
    __tablename__ = "maintenance"
    __table_args__ = (
        UniqueConstraint("org_id"),
        CheckConstraint(
            "reason IN (" + ", ".join(repr(r.value) for r in MaintenanceReason) + ")", "reason"
        ),
        # Active means a reason and a start; inactive keeps neither.
        CheckConstraint(
            "(active AND reason IS NOT NULL AND started_at IS NOT NULL)"
            " OR (NOT active AND reason IS NULL AND started_at IS NULL)",
            "active_state",
        ),
    )

    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reason: Mapped[MaintenanceReason | None] = mapped_column(String(16))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
