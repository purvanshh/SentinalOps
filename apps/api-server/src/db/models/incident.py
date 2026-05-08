from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.models.base import Base, JsonDict, TimestampMixin, UUIDPrimaryKeyMixin


class Incident(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "incidents"

    title: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False, default="unknown")
    status: Mapped[str] = mapped_column(Text, nullable=False, default="open")
    source: Mapped[str] = mapped_column(Text, nullable=False, default="prometheus")
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    raw_payload: Mapped[dict] = mapped_column(JsonDict, nullable=False, default=dict)
    incident_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    classification_confidence: Mapped[float | None] = mapped_column(nullable=True)
    classification_rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommended_workflow: Mapped[str | None] = mapped_column(Text, nullable=True)
    root_cause_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    root_cause_confidence: Mapped[float | None] = mapped_column(nullable=True)
    graph_thread_id: Mapped[str | None] = mapped_column(Text, nullable=True)

    agent_executions = relationship("AgentExecution", back_populates="incident", lazy="selectin")
    remediation_actions = relationship("RemediationAction", back_populates="incident", lazy="selectin")
    evaluations = relationship("Evaluation", back_populates="incident", lazy="selectin")
    postmortems = relationship("Postmortem", back_populates="incident", lazy="selectin")
    evidence_items = relationship("EvidenceItem", back_populates="incident", lazy="selectin")
