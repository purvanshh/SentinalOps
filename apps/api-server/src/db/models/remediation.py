import uuid

from sqlalchemy import Boolean, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.models.base import Base, JsonDict, TimestampMixin, UUIDPrimaryKeyMixin


class RemediationAction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "remediation_actions"

    incident_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
    )
    action: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict] = mapped_column(JsonDict, nullable=False, default=dict)
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    executed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    requires_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")

    incident = relationship("Incident", back_populates="remediation_actions")
