import uuid

from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from db.models.base import Base, JsonDict, TimestampMixin, UUIDPrimaryKeyMixin


class WorkflowCheckpoint(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "workflow_checkpoints"

    thread_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    incident_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
    )
    node_name: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[dict] = mapped_column(JsonDict, nullable=False, default=dict)
    state_hash: Mapped[str] = mapped_column(Text, nullable=False)
