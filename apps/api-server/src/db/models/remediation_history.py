from sqlalchemy import Boolean, Float, Text
from sqlalchemy.orm import Mapped, mapped_column

from db.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class RemediationHistory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "remediation_history"

    action_name: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    execution_time_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=60.0)
    severity_on_failure: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
