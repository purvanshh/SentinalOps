"use client";

import { useState } from "react";

import { decideApproval } from "@/services/apiClient";
import { ApprovalItem } from "@/types/dashboard";

type PendingApprovalsProps = {
  approvals: ApprovalItem[];
};

export function PendingApprovals({ approvals }: PendingApprovalsProps) {
  const [pendingIds, setPendingIds] = useState<string[]>([]);

  async function handleDecision(incidentId: string, approved: boolean) {
    setPendingIds((current) => [...current, incidentId]);
    try {
      await decideApproval(incidentId, approved, approved ? "Approved from dashboard" : "Rejected from dashboard");
    } finally {
      setPendingIds((current) => current.filter((id) => id !== incidentId));
    }
  }

  return (
    <section className="list-card">
      <div className="eyebrow">Approval Center</div>
      <h3 className="title" style={{ fontSize: "1.5rem", marginTop: 8 }}>
        Human-in-the-loop queue
      </h3>
      {approvals.map((approval) => (
        <div className="approval-row" key={approval.incident_id}>
          <div className="row-top">
            <strong>{approval.summary}</strong>
            <span className="pill warning">{approval.status}</span>
          </div>
          <div className="muted">Actions: {approval.actions.join(", ")}</div>
          <div className="muted">Expires: {approval.expires_at ?? "unknown"}</div>
          <div className="actions" style={{ marginTop: 10 }}>
            <button
              className="button primary"
              onClick={() => handleDecision(approval.incident_id, true)}
              disabled={pendingIds.includes(approval.incident_id)}
            >
              Approve
            </button>
            <button
              className="button secondary"
              onClick={() => handleDecision(approval.incident_id, false)}
              disabled={pendingIds.includes(approval.incident_id)}
            >
              Reject
            </button>
          </div>
        </div>
      ))}
    </section>
  );
}
