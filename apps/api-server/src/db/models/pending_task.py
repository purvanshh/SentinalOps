import uuid

from sqlalchemy import Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from db.models.base import Base, JsonDict, TimestampMixin, UUIDPrimaryKeyMixin


class PendingTask(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "pending_tasks"

    incident_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    task_name: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JsonDict, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
