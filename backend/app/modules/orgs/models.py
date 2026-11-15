from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models_base import Base, UuidPk


class Organization(UuidPk, Base):
    """One per installation (the UI has no multi-org); every domain table points here."""

    __tablename__ = "organization"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
