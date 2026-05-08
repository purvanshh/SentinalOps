import { ApprovalItem } from "@/types/dashboard";

type PendingApprovalsProps = {
  approvals: ApprovalItem[];
};

export function PendingApprovals({ approvals }: PendingApprovalsProps) {
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
        </div>
      ))}
    </section>
  );
}
