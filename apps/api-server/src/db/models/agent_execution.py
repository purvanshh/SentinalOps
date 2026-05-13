import uuid

from db.models.base import Base, JsonDict, TimestampMixin, UUIDPrimaryKeyMixin
from sqlalchemy import Float, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship


class AgentExecution(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "agent_executions"

    incident_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
    )
    agent_name: Mapped[str] = mapped_column(Text, nullable=False)
    input: Mapped[dict | None] = mapped_column(JsonDict, nullable=True)
    output: Mapped[dict | None] = mapped_column(JsonDict, nullable=True)
    latency: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")

    incident = relationship("Incident", back_populates="agent_executions")
