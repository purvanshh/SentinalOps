import uuid

from db.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from sqlalchemy import Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column


class ApprovalToken(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "approval_tokens"

    token: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    incident_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    expires_at: Mapped[str] = mapped_column(Text, nullable=False)
    used_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
