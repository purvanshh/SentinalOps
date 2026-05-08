import uuid

from sqlalchemy import Boolean, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from db.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class PreventionItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "prevention_items"

    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("incidents.id", ondelete="SET NULL"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="open")
    completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
