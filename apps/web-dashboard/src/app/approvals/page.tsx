import { PendingApprovals } from "@/features/approvals/PendingApprovals";
import { getApprovals } from "@/services/apiClient";

export default async function ApprovalsPage() {
  const approvals = await getApprovals();

  return (
    <div className="grid" style={{ gridTemplateColumns: "1fr", marginTop: 24 }}>
      <PendingApprovals approvals={approvals} />
    </div>
  );
}
